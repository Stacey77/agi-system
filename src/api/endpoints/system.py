"""System info endpoint — non-sensitive runtime configuration."""

from __future__ import annotations

import sys
import time
from typing import Any, Dict

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/system", tags=["system"])

_START = time.time()


@router.get("/info")
async def system_info(request: Request) -> Dict[str, Any]:
    """Return non-sensitive runtime info for dashboards and monitoring."""
    cfg = getattr(request.app.state, "settings", None)
    factory = getattr(request.app.state, "agent_factory", None)
    tool_registry = getattr(request.app.state, "tool_registry", None)
    queue = getattr(request.app.state, "task_queue", None)

    agents = []
    if factory:
        names = factory.list_agents()
        agents = [n if isinstance(n, str) else getattr(getattr(n, "config", None), "name", str(n)) for n in names]

    tools = []
    if tool_registry:
        tools = list(getattr(tool_registry, "_tools", {}).keys())

    tasks_summary: Dict[str, int] = {}
    if queue:
        for r in queue.list_all():
            tasks_summary[r.status] = tasks_summary.get(r.status, 0) + 1

    return {
        "version": "0.1.0",
        "python": sys.version.split()[0],
        "uptime_seconds": round(time.time() - _START, 1),
        "llm_provider": cfg.llm_provider if cfg else "unknown",
        "log_format": cfg.log_format if cfg else "unknown",
        "agents": agents,
        "tools": tools,
        "tasks": tasks_summary,
    }
