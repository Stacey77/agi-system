from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    agent_name: str


class MessageRequest(BaseModel):
    message: str


def _get_manager(request: Request):
    manager = getattr(request.app.state, "session_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="Session manager not initialised")
    return manager


def _get_factory(request: Request):
    return getattr(request.app.state, "agent_factory", None)


@router.post("/", status_code=201)
async def create_session(body: CreateSessionRequest, request: Request) -> Dict[str, Any]:
    manager = _get_manager(request)
    session = manager.create_session(agent_name=body.agent_name)
    return {
        "session_id": session.session_id,
        "agent_name": session.agent_name,
        "created_at": session.created_at,
    }


@router.get("/")
async def list_sessions(request: Request) -> List[Dict[str, Any]]:
    manager = _get_manager(request)
    return [
        {
            "session_id": s.session_id,
            "agent_name": s.agent_name,
            "created_at": s.created_at,
            "message_count": len(s.messages),
        }
        for s in manager.list_sessions()
    ]


@router.get("/{session_id}")
async def get_session(session_id: str, request: Request) -> Dict[str, Any]:
    manager = _get_manager(request)
    session = manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {
        "session_id": session.session_id,
        "agent_name": session.agent_name,
        "created_at": session.created_at,
        "messages": session.messages,
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request) -> Dict[str, str]:
    manager = _get_manager(request)
    removed = manager.delete_session(session_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"message": f"Session '{session_id}' deleted"}


@router.post("/{session_id}/message")
async def send_message(
    session_id: str, body: MessageRequest, request: Request
) -> Dict[str, Any]:
    manager = _get_manager(request)
    session = manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    factory = _get_factory(request)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    agent = factory.get_agent(session.agent_name)
    if agent is None:
        raise HTTPException(
            status_code=404, detail=f"Agent '{session.agent_name}' not found"
        )

    history_context = "\n".join(
        f"{m['role']}: {m['content']}" for m in session.messages
    )
    task_input = body.message
    if history_context:
        task_input = f"Conversation history:\n{history_context}\n\nUser: {body.message}"

    try:
        result = await agent.process_task({"task": task_input})
    except Exception as exc:  # noqa: BLE001
        logger.error("Agent '%s' error in session '%s': %s", session.agent_name, session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    output = result.get("result") or result.get("output") or str(result)

    manager.add_message(session_id, role="user", content=body.message)
    manager.add_message(session_id, role="assistant", content=output)

    return {"role": "assistant", "content": output}


@router.get("/{session_id}/history")
async def get_history(session_id: str, request: Request) -> List[Dict[str, Any]]:
    manager = _get_manager(request)
    session = manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session.messages
