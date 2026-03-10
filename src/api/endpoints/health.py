"""Health check endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Basic liveness probe."""
    return {"status": "healthy"}


@router.get("/health/detailed")
async def detailed_health() -> Dict[str, Any]:
    """Detailed health check including component status."""
    components: Dict[str, Any] = {}

    # Check execution engine
    try:
        from src.execution.execution_engine import ExecutionEngine  # noqa: F401
        components["execution_engine"] = "healthy"
    except Exception as exc:  # noqa: BLE001
        components["execution_engine"] = f"unhealthy: {exc}"

    # Check memory subsystem
    try:
        from src.memory.memory_manager import MemoryManager  # noqa: F401
        components["memory"] = "healthy"
    except Exception as exc:  # noqa: BLE001
        components["memory"] = f"unhealthy: {exc}"

    # Check tool registry
    try:
        from src.tools.tool_registry import ToolRegistry  # noqa: F401
        components["tool_registry"] = "healthy"
    except Exception as exc:  # noqa: BLE001
        components["tool_registry"] = f"unhealthy: {exc}"

    all_healthy = all(v == "healthy" for v in components.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components,
    }
