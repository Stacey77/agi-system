"""CDE endpoints — cloud development environment lifecycle management."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cde", tags=["cde"])


class CDECreateRequest(BaseModel):
    name: str = "my-cde"
    runtime: str = "python"
    runtime_version: str = "latest"
    owner: str = ""
    repository_url: str | None = None
    branch: str = "main"
    resources: dict[str, Any] = {}
    env_vars: dict[str, str] = {}
    tags: list[str] = []


class CDEActionRequest(BaseModel):
    action: str
    env_id: str | None = None
    parameters: dict[str, Any] = {}


def _get_cde_agent(request: Request) -> Any:
    agent = getattr(request.app.state, "cde_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="CDE agent not initialised")
    return agent


@router.post("/environments")
async def create_environment(
    body: CDECreateRequest, request: Request
) -> dict[str, Any]:
    """Provision a new cloud development environment."""
    cde_agent = _get_cde_agent(request)
    task: dict[str, Any] = {
        "action": "create",
        "name": body.name,
        "runtime": body.runtime,
        "runtime_version": body.runtime_version,
        "owner": body.owner,
        "repository_url": body.repository_url,
        "branch": body.branch,
        "resources": body.resources,
        "env_vars": body.env_vars,
        "tags": body.tags,
    }
    try:
        return await cde_agent.process_task(task)
    except Exception as exc:
        logger.error("CDE create error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/environments")
async def list_environments(
    request: Request, owner: str | None = None, status: str | None = None
) -> dict[str, Any]:
    """List CDE environments, optionally filtered by owner or status."""
    cde_agent = _get_cde_agent(request)
    task: dict[str, Any] = {"action": "list", "owner": owner, "filter_status": status}
    return await cde_agent.process_task(task)


@router.get("/environments/{env_id}")
async def get_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Get the status of a specific CDE environment."""
    cde_agent = _get_cde_agent(request)
    result = await cde_agent.process_task({"action": "status", "env_id": env_id})
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("error", "Not found"))
    return result


@router.post("/environments/{env_id}/start")
async def start_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Start a stopped CDE environment."""
    cde_agent = _get_cde_agent(request)
    result = await cde_agent.process_task({"action": "start", "env_id": env_id})
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=f"Cannot start environment '{env_id}'"
        )
    return result


@router.post("/environments/{env_id}/stop")
async def stop_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Stop a running CDE environment."""
    cde_agent = _get_cde_agent(request)
    result = await cde_agent.process_task({"action": "stop", "env_id": env_id})
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=f"Cannot stop environment '{env_id}'"
        )
    return result


@router.delete("/environments/{env_id}")
async def delete_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Delete a CDE environment."""
    cde_agent = _get_cde_agent(request)
    result = await cde_agent.process_task({"action": "delete", "env_id": env_id})
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=f"Environment '{env_id}' not found")
    return result


@router.get("/status")
async def cde_status(request: Request) -> dict[str, Any]:
    """Return CDE agent status and environment metrics."""
    cde_agent = _get_cde_agent(request)
    return {
        **cde_agent.get_status(),
        "running_environments": cde_agent.cde_manager.running_count(),
        "total_environments": cde_agent.cde_manager.total_count(),
    }
