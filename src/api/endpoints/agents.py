"""Agent management endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class TaskRequest(BaseModel):
    task: str
    parameters: Dict[str, Any] = {}


@router.get("/")
async def list_agents(request: Request) -> List[Dict[str, Any]]:
    """List all registered agents with name, type, and status."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        return []
    agents = factory.list_agents()
    return [
        {
            "name": name,
            "type": agent.config.agent_type,
            "status": "ready",
            "capabilities": agent.config.capabilities,
        }
        for name, agent in agents.items()
    ]


@router.post("/{agent_name}/execute")
async def execute_agent_task(
    agent_name: str, body: TaskRequest, request: Request
) -> Dict[str, Any]:
    """Execute a task using the named agent."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    agent = factory.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    task_dict = {"task": body.task, **body.parameters}
    try:
        result = await agent.process_task(task_dict)
        return {"agent": agent_name, "result": result}
    except Exception as exc:  # noqa: BLE001
        logger.error("Agent '%s' execution error: %s", agent_name, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{agent_name}/status")
async def agent_status(agent_name: str, request: Request) -> Dict[str, Any]:
    """Get status and memory usage for the named agent."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    agent = factory.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    return agent.get_status()
