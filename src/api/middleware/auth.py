"""API key / JWT authentication middleware."""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_EXCLUDED_PATHS = {"/health", "/health/detailed", "/docs", "/openapi.json", "/redoc", "/"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates requests via JWT bearer token or direct API key header."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _EXCLUDED_PATHS or request.url.path.startswith("/static/"):
            return await call_next(request)

        key_store = getattr(request.app.state, "key_store", None)
        jwt_manager = getattr(request.app.state, "jwt_manager", None)

        if key_store is None or not key_store.list_keys():
            logger.debug("APIKeyMiddleware: no keys configured — skipping auth (dev mode)")
            return await call_next(request)

        auth_role: str | None = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and jwt_manager is not None:
            token = auth_header[len("Bearer "):]
            payload = jwt_manager.verify_token(token)
            if payload:
                auth_role = payload.get("role")

        if auth_role is None:
            x_api_key = request.headers.get("X-API-Key", "")
            if x_api_key:
                api_key = key_store.validate_key(x_api_key)
                if api_key:
                    auth_role = api_key.role.value

        if auth_role is None:
            logger.warning(
                "Unauthorised request to '%s' from %s",
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing credentials"},
            )

        request.state.auth_role = auth_role
        return await call_next(request)
