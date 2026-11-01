"""Enterprise governance endpoints — audit, tenants, RBAC."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/enterprise", tags=["enterprise"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _audit(request: Request):
    al = getattr(request.app.state, "audit_log", None)
    if al is None:
        raise HTTPException(status_code=503, detail="Audit log not initialised")
    return al


def _tenants(request: Request):
    tm = getattr(request.app.state, "tenant_manager", None)
    if tm is None:
        raise HTTPException(status_code=503, detail="Tenant manager not initialised")
    return tm


def _rbac(request: Request):
    rb = getattr(request.app.state, "rbac_manager", None)
    if rb is None:
        raise HTTPException(status_code=503, detail="RBAC manager not initialised")
    return rb


# ── Audit log ─────────────────────────────────────────────────────────────────

class AuditLogRequest(BaseModel):
    actor: str
    action: str
    resource_type: str
    resource_id: str = ""
    details: Optional[Dict[str, Any]] = None
    ip_address: str = ""
    status: str = "success"


@router.post("/audit/events", summary="Write an audit event")
async def write_audit_event(body: AuditLogRequest, request: Request) -> Dict[str, Any]:
    al = _audit(request)
    event_id = await al.log(
        actor=body.actor,
        action=body.action,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        details=body.details,
        ip_address=body.ip_address,
        status=body.status,
    )
    return {"event_id": event_id}


@router.get("/audit/events", summary="Query audit events")
async def query_audit_events(
    actor: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    limit: int = 100,
    offset: int = 0,
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    al = _audit(request)
    return await al.query(
        actor=actor,
        action=action,
        resource_type=resource_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


@router.get("/audit/events/{event_id}", summary="Get a single audit event")
async def get_audit_event(event_id: str, request: Request) -> Dict[str, Any]:
    al = _audit(request)
    event = await al.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.delete("/audit/purge", summary="Purge audit events before a timestamp")
async def purge_audit_events(before: float, request: Request) -> Dict[str, Any]:
    al = _audit(request)
    deleted = await al.purge_before(before)
    return {"deleted": deleted}


# ── Tenants ───────────────────────────────────────────────────────────────────

class TenantCreateRequest(BaseModel):
    name: str
    plan: str = "free"
    owner_id: str = ""
    metadata: Optional[Dict[str, Any]] = None


class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None


@router.post("/tenants", summary="Create a tenant")
async def create_tenant(body: TenantCreateRequest, request: Request) -> Dict[str, Any]:
    tm = _tenants(request)
    try:
        tenant = tm.create_tenant(name=body.name, plan=body.plan, owner_id=body.owner_id, metadata=body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return tenant.to_dict()


@router.get("/tenants", summary="List tenants")
async def list_tenants(
    active_only: bool = False,
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    tm = _tenants(request)
    tenants = tm.list_tenants(active_only=active_only)
    return {"tenants": [t.to_dict() for t in tenants], "total": len(tenants)}


@router.get("/tenants/plans", summary="List available plans")
async def list_plans(request: Request) -> Dict[str, Any]:
    return _tenants(request).available_plans()


@router.get("/tenants/{tenant_id}", summary="Get a tenant")
async def get_tenant(tenant_id: str, request: Request) -> Dict[str, Any]:
    tm = _tenants(request)
    t = tm.get_tenant(tenant_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t.to_dict()


@router.patch("/tenants/{tenant_id}", summary="Update a tenant")
async def update_tenant(tenant_id: str, body: TenantUpdateRequest, request: Request) -> Dict[str, Any]:
    tm = _tenants(request)
    try:
        t = tm.update_tenant(
            tenant_id=tenant_id,
            name=body.name,
            plan=body.plan,
            metadata=body.metadata,
            active=body.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if t is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t.to_dict()


@router.delete("/tenants/{tenant_id}", summary="Delete a tenant")
async def delete_tenant(tenant_id: str, request: Request) -> Dict[str, Any]:
    tm = _tenants(request)
    ok = tm.delete_tenant(tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"deleted": tenant_id}


# ── RBAC ──────────────────────────────────────────────────────────────────────

class RoleCreateRequest(BaseModel):
    name: str
    permissions: Optional[List[str]] = None
    description: str = ""


class PermissionRequest(BaseModel):
    permission: str


class RoleAssignRequest(BaseModel):
    user_id: str
    role_name: str


@router.get("/rbac/roles", summary="List roles")
async def list_roles(request: Request) -> Dict[str, Any]:
    rb = _rbac(request)
    roles = rb.list_roles()
    return {"roles": [{"name": r.name, "description": r.description, "permissions": list(r.permissions)} for r in roles]}


@router.post("/rbac/roles", summary="Create a role")
async def create_role(body: RoleCreateRequest, request: Request) -> Dict[str, Any]:
    rb = _rbac(request)
    role = rb.create_role(name=body.name, permissions=body.permissions, description=body.description)
    return {"name": role.name, "description": role.description, "permissions": list(role.permissions)}


@router.get("/rbac/permissions", summary="List permissions")
async def list_permissions(request: Request) -> Dict[str, Any]:
    rb = _rbac(request)
    perms = rb.list_permissions()
    return {"permissions": [{"name": p.name, "description": p.description} for p in perms]}


@router.post("/rbac/assign", summary="Assign a role to a user")
async def assign_role(body: RoleAssignRequest, request: Request) -> Dict[str, Any]:
    rb = _rbac(request)
    ok = rb.assign_role(user_id=body.user_id, role_name=body.role_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"user_id": body.user_id, "role": body.role_name, "assigned": True}


@router.post("/rbac/revoke", summary="Revoke a role from a user")
async def revoke_role(body: RoleAssignRequest, request: Request) -> Dict[str, Any]:
    rb = _rbac(request)
    rb.revoke_role(user_id=body.user_id, role_name=body.role_name)
    return {"user_id": body.user_id, "role": body.role_name, "revoked": True}


@router.get("/rbac/users/{user_id}/permissions", summary="Get user effective permissions")
async def user_permissions(user_id: str, request: Request) -> Dict[str, Any]:
    rb = _rbac(request)
    perms = rb.get_user_permissions(user_id)
    return {"user_id": user_id, "permissions": list(perms), "roles": rb.get_user_roles(user_id)}
