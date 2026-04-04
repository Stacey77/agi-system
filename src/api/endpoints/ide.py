"""Vibecoding IDE endpoints — AI coding assistant and session management."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ide", tags=["ide"])


class IDESessionRequest(BaseModel):
    language: str = "python"
    context: str = ""
    metadata: Dict[str, Any] = {}


class CodeActionRequest(BaseModel):
    action: str = "complete"
    prompt: str
    language: str = "python"
    session_id: Optional[str] = None
    parameters: Dict[str, Any] = {}


def _get_ide_agent(request: Request) -> Any:
    agent = getattr(request.app.state, "ide_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="IDE agent not initialised")
    return agent


# ------------------------------------------------------------------
# Session management
# ------------------------------------------------------------------

@router.post("/sessions")
async def create_session(body: IDESessionRequest, request: Request) -> Dict[str, Any]:
    """Create a new vibecoding IDE session."""
    ide_agent = _get_ide_agent(request)
    session = ide_agent.session_manager.create_session(
        language=body.language,
        context=body.context,
        metadata=body.metadata,
    )
    return {"session": session.to_dict()}


@router.get("/sessions")
async def list_sessions(request: Request) -> Dict[str, Any]:
    """List all IDE sessions."""
    ide_agent = _get_ide_agent(request)
    sessions = ide_agent.session_manager.list_sessions()
    return {
        "sessions": [s.to_dict() for s in sessions],
        "total": len(sessions),
        "active": ide_agent.session_manager.active_count(),
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> Dict[str, Any]:
    """Get details of a specific IDE session."""
    ide_agent = _get_ide_agent(request)
    session = ide_agent.session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"session": session.to_dict()}


@router.delete("/sessions/{session_id}")
async def close_session(session_id: str, request: Request) -> Dict[str, str]:
    """Close an IDE session."""
    ide_agent = _get_ide_agent(request)
    closed = ide_agent.session_manager.close_session(session_id)
    if not closed:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"message": f"Session '{session_id}' closed"}


# ------------------------------------------------------------------
# Code actions
# ------------------------------------------------------------------

@router.post("/actions")
async def execute_code_action(body: CodeActionRequest, request: Request) -> Dict[str, Any]:
    """Execute an AI code action (complete / explain / refactor / fix / generate / review)."""
    ide_agent = _get_ide_agent(request)
    task: Dict[str, Any] = {
        "action": body.action,
        "prompt": body.prompt,
        "language": body.language,
        "session_id": body.session_id,
        **body.parameters,
    }
    try:
        return await ide_agent.process_task(task)
    except Exception as exc:  # noqa: BLE001
        logger.error("IDE action error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
async def ide_status(request: Request) -> Dict[str, Any]:
    """Return IDE agent status and session metrics."""
    ide_agent = _get_ide_agent(request)
    return {
        **ide_agent.get_status(),
        "active_sessions": ide_agent.session_manager.active_count(),
        "total_sessions": len(ide_agent.session_manager.list_sessions()),
    }
