"""Multi-tenant management for enterprise deployments."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_PLAN_LIMITS: Dict[str, Dict[str, Any]] = {
    "free":       {"agents": 3,   "requests_per_minute": 20,  "storage_mb": 512},
    "starter":    {"agents": 10,  "requests_per_minute": 100, "storage_mb": 2048},
    "pro":        {"agents": 50,  "requests_per_minute": 500, "storage_mb": 10240},
    "enterprise": {"agents": -1,  "requests_per_minute": -1,  "storage_mb": -1},
}


@dataclass
class Tenant:
    tenant_id: str
    name: str
    plan: str = "free"
    owner_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def limits(self) -> Dict[str, Any]:
        return _PLAN_LIMITS.get(self.plan, _PLAN_LIMITS["free"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "plan": self.plan,
            "owner_id": self.owner_id,
            "metadata": self.metadata,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "limits": self.limits,
        }


class TenantManager:
    """In-memory tenant registry."""

    def __init__(self) -> None:
        self._tenants: Dict[str, Tenant] = {}

    def create_tenant(
        self,
        name: str,
        plan: str = "free",
        owner_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tenant:
        if plan not in _PLAN_LIMITS:
            raise ValueError(f"Unknown plan {plan!r}; valid: {list(_PLAN_LIMITS)}")
        tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            name=name,
            plan=plan,
            owner_id=owner_id,
            metadata=metadata or {},
        )
        self._tenants[tenant.tenant_id] = tenant
        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)

    def list_tenants(self, active_only: bool = False) -> List[Tenant]:
        tenants = list(self._tenants.values())
        if active_only:
            tenants = [t for t in tenants if t.active]
        return tenants

    def update_tenant(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        plan: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        active: Optional[bool] = None,
    ) -> Optional[Tenant]:
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return None
        if name is not None:
            tenant.name = name
        if plan is not None:
            if plan not in _PLAN_LIMITS:
                raise ValueError(f"Unknown plan {plan!r}")
            tenant.plan = plan
        if metadata is not None:
            tenant.metadata.update(metadata)
        if active is not None:
            tenant.active = active
        tenant.updated_at = time.time()
        return tenant

    def delete_tenant(self, tenant_id: str) -> bool:
        if tenant_id not in self._tenants:
            return False
        del self._tenants[tenant_id]
        return True

    def available_plans(self) -> Dict[str, Any]:
        return dict(_PLAN_LIMITS)

    def __repr__(self) -> str:
        return f"TenantManager(tenants={len(self._tenants)})"
