"""Crew orchestration endpoint — multi-agent collaborative task execution."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/crew", tags=["crew"])


class CrewTaskRequest(BaseModel):
    objective: str
    agents: Optional[List[str]] = None
    stream: bool = False


@router.post("/run")
async def run_crew(body: CrewTaskRequest, request: Request) -> Dict[str, Any]:
    """Run a collaborative multi-agent crew on the given objective."""
    orchestrator = getattr(request.app.state, "crew_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Crew orchestrator not initialised")
    try:
        result = await orchestrator.run(body.objective, agent_names=body.agents)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("Crew execution error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/run/stream")
async def stream_crew(body: CrewTaskRequest, request: Request) -> StreamingResponse:
    """Stream a crew run step-by-step via Server-Sent Events."""
    orchestrator = getattr(request.app.state, "crew_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Crew orchestrator not initialised")

    factory = getattr(request.app.state, "agent_factory", None)
    agent_names = body.agents or ["research_agent", "analysis_agent", "writing_agent", "review_agent"]

    async def _generate():
        import json
        for name in agent_names:
            if factory is None:
                break
            agent = factory.get_agent(name)
            if agent is None:
                continue
            yield f"data: {json.dumps({'agent': name, 'status': 'starting'})}\n\n"
            try:
                task = {"task": body.objective}
                async for chunk in agent.stream_task(task):
                    safe = chunk.replace("\n", "\\n")
                    yield f"data: {json.dumps({'agent': name, 'chunk': safe})}\n\n"
            except Exception as exc:  # noqa: BLE001
                yield f"data: {json.dumps({'agent': name, 'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
