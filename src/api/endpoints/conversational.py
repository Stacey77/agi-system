"""Conversational AI session endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/conversational", tags=["conversational"])


class SessionCreateRequest(BaseModel):
    user_id: str
    metadata: Optional[Dict[str, Any]] = None


class MessageRequest(BaseModel):
    role: str = "user"
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ClassifyRequest(BaseModel):
    text: str
    session_id: Optional[str] = None


def _mgr(request: Request):
    mgr = getattr(request.app.state, "conversation_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Conversation manager not initialised")
    return mgr


def _clf(request: Request):
    return getattr(request.app.state, "intent_classifier", None)


@router.post("/sessions", summary="Create a new conversation session")
async def create_session(body: SessionCreateRequest, request: Request) -> Dict[str, Any]:
    mgr = _mgr(request)
    session = await mgr.create_session(user_id=body.user_id, metadata=body.metadata)
    return session


@router.get("/sessions", summary="List conversation sessions")
async def list_sessions(
    user_id: Optional[str] = None,
    limit: int = 50,
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    mgr = _mgr(request)
    sessions = await mgr.list_sessions(user_id=user_id, limit=limit)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/sessions/{session_id}", summary="Get a session")
async def get_session(session_id: str, request: Request) -> Dict[str, Any]:
    mgr = _mgr(request)
    session = await mgr.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}", summary="Delete a session")
async def delete_session(session_id: str, request: Request) -> Dict[str, Any]:
    mgr = _mgr(request)
    ok = await mgr.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": session_id}


@router.post("/sessions/{session_id}/messages", summary="Add a message to a session")
async def add_message(session_id: str, body: MessageRequest, request: Request) -> Dict[str, Any]:
    mgr = _mgr(request)
    msg = await mgr.add_message(
        session_id=session_id,
        role=body.role,
        content=body.content,
        metadata=body.metadata,
    )
    if msg is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return msg


@router.get("/sessions/{session_id}/messages", summary="Get messages for a session")
async def get_messages(
    session_id: str,
    limit: int = 100,
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    mgr = _mgr(request)
    messages = await mgr.get_messages(session_id, limit=limit)
    return {"session_id": session_id, "messages": messages, "total": len(messages)}


@router.get("/sessions/{session_id}/context", summary="Get sliding context window")
async def get_context(
    session_id: str,
    max_tokens: int = 4096,
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    mgr = _mgr(request)
    messages = await mgr.get_context_window(session_id, max_tokens=max_tokens)
    return {"session_id": session_id, "messages": messages, "max_tokens": max_tokens}


@router.post("/classify", summary="Classify intent of a user message")
async def classify_intent(body: ClassifyRequest, request: Request) -> Dict[str, Any]:
    clf = _clf(request)
    if clf is None:
        raise HTTPException(status_code=503, detail="Intent classifier not initialised")
    result = await clf.classify(body.text)
    return result
