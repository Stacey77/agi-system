"""Firebase Cloud Functions entry-point — wraps FastAPI via functions-framework."""

from __future__ import annotations

import os
import sys

# Ensure the repo root is on the path so `src/` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from firebase_functions import https_fn  # type: ignore[import]

from src.api.main import app as fastapi_app


def _client_ip(req: https_fn.Request) -> str:
    xff = req.environ.get("HTTP_X_FORWARDED_FOR", "")
    return xff.split(",")[0].strip() or req.environ.get("REMOTE_ADDR", "")


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

    # SSE streams require chunked transfer; Cloud Functions buffer the full response
    # before returning, so event-stream requests would stall until timeout.
    # Clients should poll GET /api/v1/tasks/{id} for task status instead.
    if req.headers.get("accept", "").startswith("text/event-stream"):
        return https_fn.Response(
            response=b'{"detail":"SSE streaming is not supported on this deployment. Poll GET /api/v1/tasks/{id} for task status."}',
            status=501,
            headers={"Content-Type": "application/json"},
            mimetype="application/json",
        )

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": req.method,
        "headers": [(k.lower().encode(), v.encode()) for k, v in req.headers.items()],
        "path": req.path,
        "query_string": req.query_string
        if isinstance(req.query_string, bytes)
        else req.query_string.encode(),
        "root_path": "",
        "server": ("localhost", 8080),
        "client": (_client_ip(req), 0),
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
        mimetype=response_started.get("headers", {}).get(
            "content-type", "application/json"
        ),
    )
