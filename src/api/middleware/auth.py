"""API key authentication middleware."""

from __future__ import annotations

import logging
import os
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_AUTH_HEADER = "X-API-Key"
_EXCLUDED_PATHS = {"/health", "/health/detailed", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates requests against a configured API key."""

    def __init__(self, app: ASGIApp, api_key: str | None = None) -> None:
        super().__init__(app)
        self._api_key = api_key or os.getenv("API_KEY", "")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip auth for excluded paths
        if request.url.path in _EXCLUDED_PATHS:
            return await call_next(request)

        # Skip auth if no key is configured (dev mode)
        if not self._api_key:
            logger.debug("APIKeyMiddleware: no key configured — skipping auth")
            return await call_next(request)

        provided_key = request.headers.get(_AUTH_HEADER, "")
        if provided_key != self._api_key:
            logger.warning(
                "Unauthorised request to '%s' from %s",
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
