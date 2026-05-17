"""Health check endpoints — liveness + readiness probes."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_START_TIME = time.time()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Liveness probe — always returns 200 if the process is alive."""
    return {"status": "healthy"}


@router.get("/health/detailed")
async def detailed_health(request: Request) -> Dict[str, Any]:
    """Readiness probe — checks each runtime component via app.state."""
    components: Dict[str, Any] = {}

    # Task queue
    try:
        queue = getattr(request.app.state, "task_queue", None)
        if queue is not None:
            total = len(queue.list_all())
            components["task_queue"] = {"status": "healthy", "total_tasks": total}
        else:
            components["task_queue"] = {"status": "not_initialised"}
    except Exception as exc:  # noqa: BLE001
        components["task_queue"] = {"status": "unhealthy", "error": str(exc)}

    # Redis (if configured)
    try:
        queue = getattr(request.app.state, "task_queue", None)
        if queue is not None and getattr(queue, "_redis", None) is not None:
            await queue._redis.ping()
            components["redis"] = {"status": "healthy"}
        else:
            components["redis"] = {"status": "not_configured"}
    except Exception as exc:  # noqa: BLE001
        components["redis"] = {"status": "unhealthy", "error": str(exc)}

    # LLM
    try:
        llm = getattr(request.app.state, "llm", None)
        if llm is not None:
            components["llm"] = {"status": "healthy", "provider": type(llm).__name__}
        else:
            components["llm"] = {"status": "mock_mode"}
    except Exception as exc:  # noqa: BLE001
        components["llm"] = {"status": "unhealthy", "error": str(exc)}

    # Agent factory
    try:
        factory = getattr(request.app.state, "agent_factory", None)
        if factory is not None:
            agent_names = [a.config.name for a in factory.list_agents()]
            components["agent_factory"] = {"status": "healthy", "agents": agent_names}
        else:
            components["agent_factory"] = {"status": "not_initialised"}
    except Exception as exc:  # noqa: BLE001
        components["agent_factory"] = {"status": "unhealthy", "error": str(exc)}

    # Task persistence (SQLite)
    try:
        persistence = getattr(request.app.state, "task_persistence", None)
        if persistence is not None and persistence._conn is not None:
            components["task_db"] = {"status": "healthy", "path": persistence._db_path}
        else:
            components["task_db"] = {"status": "not_configured"}
    except Exception as exc:  # noqa: BLE001
        components["task_db"] = {"status": "unhealthy", "error": str(exc)}

    # Key store
    try:
        key_store = getattr(request.app.state, "key_store", None)
        if key_store is not None:
            active = sum(1 for k in key_store.list_keys() if k.active)
            components["auth"] = {"status": "healthy", "active_keys": active}
        else:
            components["auth"] = {"status": "not_initialised"}
    except Exception as exc:  # noqa: BLE001
        components["auth"] = {"status": "unhealthy", "error": str(exc)}

    statuses = [
        v["status"] if isinstance(v, dict) else v
        for v in components.values()
    ]
    all_ok = all(s in ("healthy", "mock_mode", "not_configured") for s in statuses)

    return {
        "status": "healthy" if all_ok else "degraded",
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "components": components,
    }
