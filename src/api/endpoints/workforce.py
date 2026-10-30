"""Autonomous Intelligent Workforce endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/workforce", tags=["workforce"])


class HireRequest(BaseModel):
    name: str
    agent_type: str
    skills: List[str] = []


class ObjectiveRequest(BaseModel):
    objective: str
    required_skills: Optional[List[str]] = None


class BatchObjectiveRequest(BaseModel):
    objectives: List[str]
    required_skills: Optional[List[str]] = None


class ScaleRequest(BaseModel):
    agent_type: str
    count: int = 1


def _wm(request: Request):
    wm = getattr(request.app.state, "workforce_manager", None)
    if wm is None:
        raise HTTPException(status_code=503, detail="Workforce manager not initialised")
    return wm


@router.get("/status", summary="Workforce pool status")
async def workforce_status(request: Request) -> Dict[str, Any]:
    return _wm(request).workforce_status()


@router.post("/hire", summary="Hire a new worker")
async def hire_worker(body: HireRequest, request: Request) -> Dict[str, Any]:
    wm = _wm(request)
    return await wm.hire(name=body.name, agent_type=body.agent_type, skills=body.skills)


@router.delete("/workers/{worker_id}", summary="Fire a worker")
async def fire_worker(worker_id: str, request: Request) -> Dict[str, Any]:
    wm = _wm(request)
    ok = await wm.fire(worker_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Worker not found")
    return {"fired": worker_id}


@router.post("/assign", summary="Assign a single objective to an available worker")
async def assign_objective(body: ObjectiveRequest, request: Request) -> Dict[str, Any]:
    wm = _wm(request)
    return await wm.assign_objective(
        objective=body.objective, required_skills=body.required_skills
    )


@router.post("/assign/batch", summary="Assign multiple objectives")
async def assign_batch(body: BatchObjectiveRequest, request: Request) -> Dict[str, Any]:
    wm = _wm(request)
    results = await wm.assign_batch(
        objectives=body.objectives, required_skills=body.required_skills
    )
    return {"assignments": results, "total": len(results)}


@router.post("/scale", summary="Scale up workers of a given type")
async def scale_up(body: ScaleRequest, request: Request) -> Dict[str, Any]:
    wm = _wm(request)
    workers = await wm.scale_up(agent_type=body.agent_type, count=body.count)
    return {"hired": workers, "count": len(workers)}


@router.get("/workers", summary="List all workers")
async def list_workers(
    status: Optional[str] = None,
    skill: Optional[str] = None,
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    wm = _wm(request)
    pool = wm._pool
    workers = pool.list_workers(status=status, skill=skill)
    return {"workers": [w.to_dict() for w in workers], "total": len(workers)}


@router.post("/initialize", summary="Initialise workforce from registered agents")
async def initialize_workforce(request: Request) -> Dict[str, Any]:
    wm = _wm(request)
    await wm.initialize_from_factory()
    return wm.workforce_status()
