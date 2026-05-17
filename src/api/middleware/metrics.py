"""Prometheus metrics middleware and instrumented agent wrapper."""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed — metrics disabled")

if _PROMETHEUS_AVAILABLE:
    HTTP_REQUESTS_TOTAL = Counter(
        "agi_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    HTTP_REQUEST_DURATION = Histogram(
        "agi_http_request_duration_seconds",
        "HTTP request duration",
        ["method", "path"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    )
    AGENT_TASKS_TOTAL = Counter(
        "agi_agent_tasks_total",
        "Total agent task executions",
        ["agent_name", "status"],
    )
    AGENT_TASK_DURATION = Histogram(
        "agi_agent_task_duration_seconds",
        "Agent task execution duration",
        ["agent_name"],
        buckets=[0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    )
    CREW_RUNS_TOTAL = Counter(
        "agi_crew_runs_total",
        "Total crew run executions",
        ["engine", "status"],
    )
    WS_CONNECTIONS_ACTIVE = Gauge(
        "agi_websocket_connections_active",
        "Currently active WebSocket connections",
    )


def record_agent_task(agent_name: str, status: str, duration_s: float) -> None:
    """Record agent task metrics — safe no-op if prometheus not available."""
    if not _PROMETHEUS_AVAILABLE:
        return
    AGENT_TASKS_TOTAL.labels(agent_name=agent_name, status=status).inc()
    AGENT_TASK_DURATION.labels(agent_name=agent_name).observe(duration_s)


def record_crew_run(engine: str, status: str) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    CREW_RUNS_TOTAL.labels(engine=engine, status=status).inc()


def ws_connection_open() -> None:
    if _PROMETHEUS_AVAILABLE:
        WS_CONNECTIONS_ACTIVE.inc()


def ws_connection_close() -> None:
    if _PROMETHEUS_AVAILABLE:
        WS_CONNECTIONS_ACTIVE.dec()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records HTTP request counts and durations in Prometheus."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        if _PROMETHEUS_AVAILABLE:
            duration = time.perf_counter() - start
            path = _normalise_path(request)
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method, path=path, status=response.status_code
            ).inc()
            HTTP_REQUEST_DURATION.labels(method=request.method, path=path).observe(duration)
        return response


def _normalise_path(request: Request) -> str:
    """Replace path parameters with placeholders for cardinality control."""
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return request.url.path


def metrics_response() -> Response:
    """Return a Prometheus /metrics response."""
    if not _PROMETHEUS_AVAILABLE:
        return Response("# prometheus_client not installed\n", media_type="text/plain")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
