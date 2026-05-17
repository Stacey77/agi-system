"""Token-bucket rate limiting middleware — per API key or IP address.

Admin-role keys bypass rate limiting entirely.
Write-role keys get the configured limit.
Read-role keys get half the configured limit.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Callable, Dict

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

    Rate limits are role-aware:
        admin  — unlimited (bypass)
        write  — full RATE_LIMIT_REQUESTS capacity
        read   — half capacity
        unknown — full capacity (no key presented)
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        from src.config import get_settings
        cfg = get_settings()
        self._capacity = float(cfg.rate_limit_requests)
        self._refill_rate = self._capacity / cfg.rate_limit_window
        self._buckets: Dict[str, _Bucket] = defaultdict(lambda: _Bucket(self._capacity))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _EXCLUDED_PATHS or request.url.path.startswith("/static/"):
            return await call_next(request)

        # Determine role from auth state (set by APIKeyMiddleware which runs first)
        auth_role = getattr(getattr(request, "state", None), "auth_role", None)

        # Admin keys bypass rate limiting entirely
        if auth_role == "admin":
            return await call_next(request)

        # Capacity multiplier: read keys get 50% of configured limit
        capacity_mult = 0.5 if auth_role == "read" else 1.0
        effective_capacity = self._capacity * capacity_mult
        effective_refill = self._refill_rate * capacity_mult

        client_id = (
            request.headers.get("X-API-Key")
            or (request.client.host if request.client else "unknown")
        )
        bucket = self._buckets[client_id]
        if not bucket.consume(effective_capacity, effective_refill):
            logger.warning("Rate limit exceeded for client '%s' (role=%s)", client_id, auth_role)
            try:
                from src.api.middleware.metrics import record_rate_limit_hit
                record_rate_limit_hit(auth_role or "unknown")
            except Exception:  # noqa: BLE001
                pass
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded — try again shortly"},
                headers={"Retry-After": str(int(1 / self._refill_rate))},
            )

        # Expose rate limit state in response headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(int(effective_capacity))
        response.headers["X-RateLimit-Remaining"] = str(int(max(0, bucket.tokens)))
        return response
