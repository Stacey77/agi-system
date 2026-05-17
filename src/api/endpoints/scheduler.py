"""Scheduled/recurring task endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/api/v1/schedules", tags=["tasks"])


class ScheduleRequest(BaseModel):
    objective: str
    interval_seconds: float
    parameters: Dict[str, Any] = {}
    run_immediately: bool = False

    @field_validator("interval_seconds")
    @classmethod
    def _min_interval(cls, v: float) -> float:
        if v < 1.0:
            raise ValueError("interval_seconds must be >= 1")
        return v


@router.post("/")
async def create_schedule(body: ScheduleRequest, request: Request) -> Dict[str, Any]:
    """Create a recurring task that fires every interval_seconds."""
    scheduler = getattr(request.app.state, "task_scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Task scheduler not initialised")
    sched = scheduler.schedule(
        objective=body.objective,
        interval_seconds=body.interval_seconds,
        parameters=body.parameters,
        run_immediately=body.run_immediately,
    )
    return sched.to_dict()


@router.get("/")
async def list_schedules(request: Request) -> List[Dict[str, Any]]:
    """List all active schedules."""
    scheduler = getattr(request.app.state, "task_scheduler", None)
    if scheduler is None:
        return []
    return [s.to_dict() for s in scheduler.list_schedules()]


@router.get("/{schedule_id}")
async def get_schedule(schedule_id: str, request: Request) -> Dict[str, Any]:
    """Get a specific schedule."""
    scheduler = getattr(request.app.state, "task_scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Task scheduler not initialised")
    sched = scheduler.get(schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return sched.to_dict()


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str, request: Request) -> Dict[str, str]:
    """Remove a schedule."""
    scheduler = getattr(request.app.state, "task_scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Task scheduler not initialised")
    if not scheduler.unschedule(schedule_id):
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return {"message": f"Schedule '{schedule_id}' removed"}


@router.post("/{schedule_id}/pause")
async def pause_schedule(schedule_id: str, request: Request) -> Dict[str, Any]:
    """Pause a schedule without removing it."""
    scheduler = getattr(request.app.state, "task_scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Task scheduler not initialised")
    if not scheduler.pause(schedule_id):
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return scheduler.get(schedule_id).to_dict()


@router.post("/{schedule_id}/resume")
async def resume_schedule(schedule_id: str, request: Request) -> Dict[str, Any]:
    """Resume a paused schedule."""
    scheduler = getattr(request.app.state, "task_scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Task scheduler not initialised")
    if not scheduler.resume(schedule_id):
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return scheduler.get(schedule_id).to_dict()
