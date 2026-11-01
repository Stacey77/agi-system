"""Request body size limiting middleware."""

from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(10 * 1024 * 1024)))  # 10 MB


class BodyLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds *max_bytes* (default 10 MB)."""

    def __init__(self, app, max_bytes: int = _DEFAULT_MAX_BYTES) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._max_bytes:
                    logger.warning(
                        "Request body too large: %s bytes (limit %s)",
                        content_length,
                        self._max_bytes,
                    )
                    return Response(
                        content='{"detail":"Request body too large"}',
                        status_code=413,
                        media_type="application/json",
                    )
            except ValueError:
                pass
        else:
            # No Content-Length (chunked transfer) — stream and count bytes
            received = 0
            chunks = []
            async for chunk in request.stream():
                received += len(chunk)
                if received > self._max_bytes:
                    logger.warning(
                        "Chunked request body too large: >%s bytes (limit %s)",
                        received,
                        self._max_bytes,
                    )
                    return Response(
                        content='{"detail":"Request body too large"}',
                        status_code=413,
                        media_type="application/json",
                    )
                chunks.append(chunk)

            # Re-inject the already-read body so downstream can read it
            async def _body_stream():
                for c in chunks:
                    yield c

            request._stream = _body_stream()  # type: ignore[attr-defined]

        return await call_next(request)
