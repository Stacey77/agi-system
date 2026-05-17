"""Task management endpoints — async queue-backed submission with SSE progress."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.tasks.queue import TaskRecord, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskSubmission(BaseModel):
    objective: str
    parameters: Dict[str, Any] = {}


@router.post("/")
async def submit_task(body: TaskSubmission, request: Request) -> Dict[str, Any]:
    """Submit a task to the async queue; returns task_id immediately."""
    queue = getattr(request.app.state, "task_queue", None)
    if queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialised")

    record = await queue.submit(body.objective, body.parameters)
    return {"task_id": record.task_id, "status": record.status, "objective": record.objective}


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request) -> Dict[str, Any]:
    """Get the current status and result of a task."""
    queue = getattr(request.app.state, "task_queue", None)
    if queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialised")

    record = queue.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return record.to_dict()


@router.get("/")
async def list_tasks(request: Request) -> Dict[str, Any]:
    """List all tasks with their statuses."""
    queue = getattr(request.app.state, "task_queue", None)
    if queue is None:
        return {"tasks": [], "total": 0}

    records = queue.list_all()
    by_status: Dict[str, int] = {}
    for r in records:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    # Push current counts to Prometheus gauges
    try:
        from src.api.middleware.metrics import update_task_queue_metrics
        update_task_queue_metrics(by_status)
    except Exception:  # noqa: BLE001
        pass

    return {
        "tasks": [r.to_dict() for r in records],
        "total": len(records),
        "by_status": by_status,
    }


@router.delete("/{task_id}")
async def cancel_task(task_id: str, request: Request) -> Dict[str, str]:
    """Cancel a queued or running task."""
    queue = getattr(request.app.state, "task_queue", None)
    if queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialised")

    if not queue.cancel(task_id):
        record = queue.get(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        return {"message": f"Task '{task_id}' cannot be cancelled (status={record.status})"}
    return {"message": f"Task '{task_id}' cancelled"}


@router.post("/{task_id}/retry")
async def retry_task(task_id: str, request: Request) -> Dict[str, Any]:
    """Re-queue a FAILED or CANCELLED task with the same objective."""
    queue = getattr(request.app.state, "task_queue", None)
    if queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialised")

    record = queue.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    if record.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail=f"Only FAILED or CANCELLED tasks can be retried (current status={record.status})",
        )

    new_record = await queue.submit(
        record.objective,
        getattr(record, "parameters", {}),
    )
    logger.info("Task '%s' retried as new task '%s'", task_id, new_record.task_id)
    return {
        "original_task_id": task_id,
        "new_task_id": new_record.task_id,
        "status": new_record.status,
        "objective": new_record.objective,
    }


@router.get("/{task_id}/stream")
async def stream_task_progress(task_id: str, request: Request) -> StreamingResponse:
    """Stream task progress events via Server-Sent Events until completion."""
    queue = getattr(request.app.state, "task_queue", None)
    if queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialised")

    record = queue.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    async def _generate():
        if record.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            yield f"data: {json.dumps(record.to_dict())}\n\n"
            yield "data: [DONE]\n\n"
            return

        sub_q = await queue.subscribe(task_id)
        try:
            yield f"data: {json.dumps(record.to_dict())}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(sub_q.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("status") in (
                        TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
                    ):
                        break
                except asyncio.TimeoutError:
                    yield "data: {\"heartbeat\": true}\n\n"
        finally:
            queue.unsubscribe(task_id, sub_q)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
