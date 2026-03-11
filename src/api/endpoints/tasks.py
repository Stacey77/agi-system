"""Task management endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# In-memory task store (production would use Redis/DB)
_tasks: Dict[str, Dict[str, Any]] = {}


class TaskSubmission(BaseModel):
    objective: str
    parameters: Dict[str, Any] = {}


@router.post("/")
async def submit_task(body: TaskSubmission, request: Request) -> Dict[str, Any]:
    """Submit a complex task to the AGI system."""
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "task_id": task_id,
        "objective": body.objective,
        "status": "pending",
        "result": None,
    }

    execution_agent = getattr(request.app.state, "execution_agent", None)
    if execution_agent is None:
        _tasks[task_id]["status"] = "queued"
        return {"task_id": task_id, "status": "queued"}

    _tasks[task_id]["status"] = "running"
    try:
        plan: Dict[str, Any] = {
            "tasks": [
                {
                    "task_id": f"{task_id}_main",
                    "action": "process",
                    "objective": body.objective,
                    **body.parameters,
                }
            ],
            "dependencies": {},
        }
        result = await execution_agent.execute_plan(plan)
        _tasks[task_id].update({"status": "completed", "result": result})
    except Exception as exc:  # noqa: BLE001
        logger.error("Task '%s' failed: %s", task_id, exc)
        _tasks[task_id].update({"status": "failed", "error": str(exc)})

    return {"task_id": task_id, "status": _tasks[task_id]["status"]}


@router.get("/{task_id}")
async def get_task(task_id: str) -> Dict[str, Any]:
    """Get the status and result of a task."""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


@router.delete("/{task_id}")
async def cancel_task(task_id: str) -> Dict[str, str]:
    """Cancel a running task."""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    if task["status"] not in ("pending", "queued", "running"):
        return {"message": f"Task '{task_id}' cannot be cancelled (status={task['status']})"}
    _tasks[task_id]["status"] = "cancelled"
    return {"message": f"Task '{task_id}' cancelled"}
