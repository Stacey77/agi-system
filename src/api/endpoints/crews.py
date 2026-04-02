"""Crew management endpoints — CrewAI-based multi-agent orchestration."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.integrations.crewai_integration import CrewBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/crews", tags=["crews"])


class CrewTaskRequest(BaseModel):
    description: str
    expected_output: str = "A comprehensive result addressing the task."


class CrewRunRequest(BaseModel):
    objective: str
    agent_names: List[str] = []
    tasks: List[CrewTaskRequest] = []


@router.post("/run")
async def run_crew(body: CrewRunRequest, request: Request) -> Dict[str, Any]:
    """Assemble and run a CrewAI crew from registered agents.

    - **objective**: High-level goal for the crew.
    - **agent_names**: Names of registered agents to include.
      When empty, all available agents are used.
    - **tasks**: Explicit task list.  When empty, a single task derived
      from the objective is created automatically.
    """
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    all_agents = factory.list_agents()

    # Resolve agent configs
    if body.agent_names:
        missing = [n for n in body.agent_names if n not in all_agents]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Agents not found: {missing}",
            )
        configs = [all_agents[n].config for n in body.agent_names]
    else:
        configs = [agent.config for agent in all_agents.values()]

    # Build task list
    tasks: List[Dict[str, Any]] = (
        [{"description": t.description, "expected_output": t.expected_output} for t in body.tasks]
        if body.tasks
        else [{"description": body.objective, "expected_output": "Complete analysis and response"}]
    )

    builder = CrewBuilder()
    try:
        result = await builder.run(
            agent_configs=configs,
            tasks=tasks,
            objective=body.objective,
        )
        return {
            "objective": body.objective,
            "success": result.success,
            "output": result.output,
            "task_outputs": result.task_outputs,
            "used_mock": result.used_mock,
            "error": result.error,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Crew run failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/agents")
async def list_crew_capable_agents(request: Request) -> List[Dict[str, Any]]:
    """List agents available for crew assembly."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        return []
    return [
        {
            "name": name,
            "type": agent.config.agent_type,
            "description": agent.config.description,
            "capabilities": agent.config.capabilities,
        }
        for name, agent in factory.list_agents().items()
    ]
