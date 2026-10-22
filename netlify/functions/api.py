"""Netlify Function entry-point — wraps the FastAPI ASGI app via mangum."""

from __future__ import annotations

try:
    from mangum import Mangum  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "mangum is required for Netlify Functions. "
        "Add 'mangum>=0.17.0' to requirements.txt."
    ) from exc

from src.api.main import app

# Mangum adapts ASGI (FastAPI) to the AWS Lambda / Netlify Functions handler
# signature: handler(event, context) -> dict
handler = Mangum(app, lifespan="off")
