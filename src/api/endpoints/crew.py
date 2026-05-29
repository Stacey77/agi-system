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


class CrewTemplate(BaseModel):
    name: str
    description: str = ""
    agent_names: List[str]
    max_iterations: int = 3


class TemplateRunRequest(BaseModel):
    objective: str


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


# ---------------------------------------------------------------------------
# Crew template endpoints
# ---------------------------------------------------------------------------


@router.post("/templates", status_code=201)
async def create_template(template: CrewTemplate, request: Request) -> CrewTemplate:
    """Create a named, reusable crew template."""
    templates: Dict[str, CrewTemplate] = getattr(request.app.state, "crew_templates", {})
    if template.name in templates:
        raise HTTPException(status_code=409, detail=f"Template '{template.name}' already exists")
    templates[template.name] = template
    request.app.state.crew_templates = templates
    return template


@router.get("/templates")
async def list_templates(request: Request) -> List[CrewTemplate]:
    """List all stored crew templates."""
    templates: Dict[str, CrewTemplate] = getattr(request.app.state, "crew_templates", {})
    return list(templates.values())


@router.get("/templates/{name}")
async def get_template(name: str, request: Request) -> CrewTemplate:
    """Retrieve a single crew template by name."""
    templates: Dict[str, CrewTemplate] = getattr(request.app.state, "crew_templates", {})
    if name not in templates:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    return templates[name]


@router.delete("/templates/{name}", status_code=204)
async def delete_template(name: str, request: Request) -> None:
    """Delete a crew template by name."""
    templates: Dict[str, CrewTemplate] = getattr(request.app.state, "crew_templates", {})
    if name not in templates:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    del templates[name]


@router.post("/templates/{name}/run")
async def run_template(name: str, body: TemplateRunRequest, request: Request) -> Dict[str, Any]:
    """Run a named crew template with a given objective."""
    templates: Dict[str, CrewTemplate] = getattr(request.app.state, "crew_templates", {})
    if name not in templates:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")

    template = templates[name]
    orchestrator = getattr(request.app.state, "crew_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Crew orchestrator not initialised")

    try:
        result = await orchestrator.run(body.objective, agent_names=template.agent_names)
        result["template"] = name
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("Template '%s' execution error: %s", name, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
