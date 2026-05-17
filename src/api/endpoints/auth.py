from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.auth.key_store import KeyRole

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    role: str


class CreateKeyRequest(BaseModel):
    name: str
    role: str = "write"


class CreateKeyResponse(BaseModel):
    key_id: str
    api_key: str
    role: str


class KeyInfo(BaseModel):
    key_id: str
    name: str
    role: str
    active: bool
    created_at: float


def _resolve_auth(request: Request) -> Optional[dict]:
    key_store = request.app.state.key_store
    jwt_manager = request.app.state.jwt_manager

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        payload = jwt_manager.verify_token(token)
        if payload:
            return payload

    x_api_key = request.headers.get("X-API-Key", "")
    if x_api_key:
        api_key = key_store.validate_key(x_api_key)
        if api_key:
            return {"sub": api_key.key_id, "name": api_key.name, "role": api_key.role.value}

    return None


def _require_admin(request: Request) -> dict:
    auth = _resolve_auth(request)
    if auth is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if auth.get("role") != KeyRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin role required")
    return auth


@router.post("/token", response_model=TokenResponse)
async def issue_token(body: TokenRequest, request: Request) -> TokenResponse:
    key_store = request.app.state.key_store
    jwt_manager = request.app.state.jwt_manager

    api_key = key_store.validate_key(body.api_key)
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    token = jwt_manager.create_token(
        key_id=api_key.key_id,
        name=api_key.name,
        role=api_key.role.value,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=jwt_manager._expiry_seconds,
        role=api_key.role.value,
    )


@router.post("/keys", response_model=CreateKeyResponse)
async def create_key(body: CreateKeyRequest, request: Request) -> CreateKeyResponse:
    _require_admin(request)
    key_store = request.app.state.key_store

    try:
        role = KeyRole(body.role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid role: {body.role}")

    raw_key, api_key = key_store.create_key(name=body.name, role=role)
    return CreateKeyResponse(
        key_id=api_key.key_id,
        api_key=raw_key,
        role=api_key.role.value,
    )


@router.get("/keys", response_model=List[KeyInfo])
async def list_keys(request: Request) -> List[KeyInfo]:
    _require_admin(request)
    key_store = request.app.state.key_store
    return [
        KeyInfo(
            key_id=k.key_id,
            name=k.name,
            role=k.role.value,
            active=k.active,
            created_at=k.created_at,
        )
        for k in key_store.list_keys()
    ]


@router.delete("/keys/{key_id}")
async def revoke_key(key_id: str, request: Request) -> dict:
    _require_admin(request)
    key_store = request.app.state.key_store
    if not key_store.revoke_key(key_id):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"revoked": key_id}


@router.get("/me")
async def me(request: Request) -> dict:
    auth = _resolve_auth(request)
    if auth is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"sub": auth.get("sub"), "name": auth.get("name"), "role": auth.get("role")}
