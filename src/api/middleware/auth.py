"""API key / JWT authentication middleware."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_EXCLUDED_PATHS = {
    "/health",
    "/health/detailed",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
}

# Maps URL path prefixes to resource names used by RBAC and audit log.
_RESOURCE_MAP: list[tuple[str, str]] = [
    ("/api/v1/agents", "agents"),
    ("/api/v1/tasks", "tasks"),
    ("/api/v1/workforce", "workforce"),
    ("/api/v1/memory", "memory"),
    ("/api/v1/enterprise", "admin"),
    ("/api/v1/sessions", "sessions"),
    ("/api/v1/auth", "auth"),
]


def _get_resource(path: str) -> str:
    for prefix, resource in _RESOURCE_MAP:
        if path.startswith(prefix):
            return resource
    return "system"


def _get_permission(method: str, resource: str) -> str:
    if method == "GET":
        return f"{resource}:read"
    if method == "DELETE":
        return f"{resource}:delete"
    return f"{resource}:write"


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates requests via JWT bearer token or direct API key header."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _EXCLUDED_PATHS or request.url.path.startswith(
            "/static/"
        ):
            return await call_next(request)

        key_store = getattr(request.app.state, "key_store", None)
        jwt_manager = getattr(request.app.state, "jwt_manager", None)

        if key_store is None or not key_store.list_keys():
            logger.debug(
                "APIKeyMiddleware: no keys configured — skipping auth (dev mode)"
            )
            return await call_next(request)

        auth_role: str | None = None
        auth_identity: str | None = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and jwt_manager is not None:
            token = auth_header[len("Bearer ") :]
            payload = jwt_manager.verify_token(token)
            if payload:
                auth_role = payload.get("role")
                auth_identity = payload.get("sub")

        if auth_role is None:
            x_api_key = request.headers.get("X-API-Key", "")
            if x_api_key:
                api_key = key_store.validate_key(x_api_key)
                if api_key:
                    auth_role = api_key.role.value
                    auth_identity = api_key.key_id

        if auth_role is None:
            logger.warning(
                "Unauthorised request to '%s' from %s",
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing credentials"},
            )

        request.state.auth_role = auth_role
        request.state.auth_identity = auth_identity

        # RBAC permission check
        rbac_manager = getattr(request.app.state, "rbac_manager", None)
        resource = _get_resource(request.url.path)
        permission = _get_permission(request.method, resource)

        if rbac_manager is not None and auth_identity is not None:
            # Only enforce if the identity has an explicitly assigned role in RBAC.
            user_roles = rbac_manager.get_user_roles(auth_identity)
            if user_roles:
                allowed = rbac_manager.check_permission(auth_identity, permission)
                if not allowed:
                    logger.warning(
                        "RBAC denied %s permission=%s for identity=%s",
                        request.url.path,
                        permission,
                        auth_identity,
                    )
                    _fire_audit(
                        request.app,
                        auth_identity,
                        request.method,
                        resource,
                        request.url.path,
                        request.client.host if request.client else "",
                        "denied",
                    )
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Insufficient permissions"},
                    )

        response = await call_next(request)

        _fire_audit(
            request.app,
            auth_identity or "unknown",
            request.method,
            resource,
            request.url.path,
            request.client.host if request.client else "",
            "success",
        )

        return response


def _fire_audit(
    app: object,
    actor: str,
    action: str,
    resource: str,
    path: str,
    ip: str,
    status: str,
) -> None:
    audit_log = getattr(app, "state", None)
    if audit_log is not None:
        audit_log = getattr(audit_log, "audit_log", None)
    if audit_log is None:
        return
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(
            audit_log.log(
                actor=actor,
                action=action,
                resource_type=resource,
                resource_id=path,
                details={"path": path, "status": status},
                ip_address=ip,
                status=status,
            )
        )
    except RuntimeError:
        # No running event loop — skip audit in test contexts that call outside loop.
        pass
