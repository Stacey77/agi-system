"""LLM token usage and cost tracking endpoints."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1/usage", tags=["system"])


@router.get("/")
async def usage_summary(request: Request) -> Dict[str, Any]:
    """Return aggregate token usage and estimated cost by agent."""
    tracker = getattr(request.app.state, "token_tracker", None)
    if tracker is None:
        return {"total_tokens": 0, "total_estimated_cost_usd": 0.0, "by_agent": {}}
    return tracker.summary()


@router.get("/tasks/{task_id}")
async def usage_for_task(task_id: str, request: Request) -> List[Dict[str, Any]]:
    """Return token usage records for a specific task."""
    tracker = getattr(request.app.state, "token_tracker", None)
    if tracker is None:
        return []
    return tracker.records_for_task(task_id)
