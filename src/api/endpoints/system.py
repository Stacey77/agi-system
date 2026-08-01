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
        "version": "1.0.0-rc.1",
        "python": sys.version.split()[0],
        "uptime_seconds": round(time.time() - _START, 1),
        "llm_provider": cfg.llm_provider if cfg else "unknown",
        "log_format": cfg.log_format if cfg else "unknown",
        "agents": agents,
        "tools": tools,
        "tasks": tasks_summary,
    }


@router.get("/auth-status")
async def auth_status(request: Request) -> Dict[str, Any]:
    """Return whether authentication is enforced.

    Intended for use by operators and monitoring systems to detect
    misconfigured (open) deployments.
    """
    key_store = getattr(request.app.state, "key_store", None)
    configured_keys = key_store.list_keys() if key_store is not None else []
    auth_enforced = len(configured_keys) > 0

    import os
    jwt_secret_stable = bool(os.getenv("JWT_SECRET"))

    return {
        "auth_enforced": auth_enforced,
        "api_keys_configured": len(configured_keys),
        "jwt_secret_stable": jwt_secret_stable,
        "warning": (
            None
            if auth_enforced
            else "Authentication is DISABLED — no API keys configured. All endpoints are publicly accessible."
        ),
    }
