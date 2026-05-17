"""Token-bucket rate limiting middleware — per API key or IP address."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Callable, Dict, Tuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_EXCLUDED_PATHS = {"/health", "/health/detailed", "/docs", "/openapi.json", "/redoc", "/"}


class _Bucket:
    """Token-bucket state for one client."""

    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float) -> None:
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def consume(self, capacity: float, refill_rate: float) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(capacity, self.tokens + elapsed * refill_rate)
        self.last_refill = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window token-bucket rate limiter.

    Configuration via env vars:
        RATE_LIMIT_REQUESTS — max requests per window (default 60)
        RATE_LIMIT_WINDOW   — window size in seconds (default 60)
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._capacity = float(os.getenv("RATE_LIMIT_REQUESTS", "60"))
        window = float(os.getenv("RATE_LIMIT_WINDOW", "60"))
        self._refill_rate = self._capacity / window
        self._buckets: Dict[str, _Bucket] = defaultdict(lambda: _Bucket(self._capacity))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _EXCLUDED_PATHS or request.url.path.startswith("/static/"):
            return await call_next(request)

        client_id = (
            request.headers.get("X-API-Key")
            or (request.client.host if request.client else "unknown")
        )
        bucket = self._buckets[client_id]
        if not bucket.consume(self._capacity, self._refill_rate):
            logger.warning("Rate limit exceeded for client '%s'", client_id)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded — try again shortly"},
                headers={"Retry-After": str(int(1 / self._refill_rate))},
            )
        return await call_next(request)
