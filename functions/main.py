"""Firebase Cloud Functions entry-point — wraps FastAPI via functions-framework."""

from __future__ import annotations

import sys
import os

# Ensure the repo root is on the path so `src/` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import functions_framework  # type: ignore[import]
from firebase_functions import https_fn  # type: ignore[import]

from src.api.main import app as fastapi_app

# functions-framework + firebase-functions ASGI bridge
# https://firebase.google.com/docs/functions/http-events?gen=2nd#python
@https_fn.on_request(
    region="us-central1",
    memory=512,
    timeout_sec=60,
    max_instances=10,
)
def api(req: https_fn.Request) -> https_fn.Response:
    """Route all HTTP requests through the FastAPI app."""
    import asyncio
    from io import BytesIO

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": req.method,
        "headers": [(k.lower().encode(), v.encode()) for k, v in req.headers.items()],
        "path": req.path,
        "query_string": req.query_string if isinstance(req.query_string, bytes) else req.query_string.encode(),
        "root_path": "",
        "server": ("localhost", 8080),
    }

    body = req.get_data()
    response_started = {}
    response_body = BytesIO()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            response_started["status"] = message["status"]
            response_started["headers"] = {
                k.decode(): v.decode() for k, v in message.get("headers", [])
            }
        elif message["type"] == "http.response.body":
            response_body.write(message.get("body", b""))

    asyncio.run(fastapi_app(scope, receive, send))

    return https_fn.Response(
        response=response_body.getvalue(),
        status=response_started.get("status", 200),
        headers=response_started.get("headers", {}),
        mimetype=response_started.get("headers", {}).get("content-type", "application/json"),
    )
