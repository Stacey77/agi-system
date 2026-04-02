"""Developer portal — internal and external developer platform management."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class PortalTier(str, Enum):
    """Developer portal audience tier."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class ServiceStatus(str, Enum):
    """Operational status of a registered service."""

    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OUTAGE = "outage"
    MAINTENANCE = "maintenance"


@dataclass
class DeveloperService:
    """A service registered in the developer portal."""

    service_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    tier: PortalTier = PortalTier.INTERNAL
    version: str = "v1"
    api_base_url: Optional[str] = None
    docs_url: Optional[str] = None
    status: ServiceStatus = ServiceStatus.OPERATIONAL
    owner_team: str = ""
    tags: List[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "description": self.description,
            "tier": self.tier,
            "version": self.version,
            "api_base_url": self.api_base_url,
            "docs_url": self.docs_url,
            "status": self.status,
            "owner_team": self.owner_team,
            "tags": self.tags,
            "registered_at": self.registered_at.isoformat(),
        }


# Built-in platform services
_DEFAULT_SERVICES: List[Dict[str, Any]] = [
    {
        "name": "AGI Task API",
        "description": "Submit and track AGI tasks",
        "tier": PortalTier.EXTERNAL,
        "version": "v1",
        "api_base_url": "/api/v1/tasks",
        "docs_url": "/docs",
        "owner_team": "platform",
        "tags": ["tasks", "ai"],
    },
    {
        "name": "AGI Agents API",
        "description": "Direct agent execution and status",
        "tier": PortalTier.EXTERNAL,
        "version": "v1",
        "api_base_url": "/api/v1/agents",
        "docs_url": "/docs",
        "owner_team": "platform",
        "tags": ["agents", "ai"],
    },
    {
        "name": "Vibecoding IDE API",
        "description": "AI-powered coding assistant and IDE sessions",
        "tier": PortalTier.EXTERNAL,
        "version": "v1",
        "api_base_url": "/api/v1/ide",
        "docs_url": "/docs",
        "owner_team": "platform",
        "tags": ["ide", "coding"],
    },
    {
        "name": "CDE Management API",
        "description": "Cloud development environment lifecycle",
        "tier": PortalTier.EXTERNAL,
        "version": "v1",
        "api_base_url": "/api/v1/cde",
        "docs_url": "/docs",
        "owner_team": "platform",
        "tags": ["cde", "environments"],
    },
    {
        "name": "Platform Tooling API",
        "description": "Platform tool landscape and discovery",
        "tier": PortalTier.BOTH if False else PortalTier.INTERNAL,
        "version": "v1",
        "api_base_url": "/api/v1/platform/tools",
        "docs_url": "/docs",
        "owner_team": "platform",
        "tags": ["tools", "catalog"],
    },
    {
        "name": "Kally AI Feedback API",
        "description": "Closed-loop feedback and system health",
        "tier": PortalTier.INTERNAL,
        "version": "v1",
        "api_base_url": "/api/v1/kally",
        "docs_url": "/docs",
        "owner_team": "ai",
        "tags": ["kally", "feedback", "ai"],
    },
]


class DeveloperPortal:
    """Internal and external developer platform portal.

    Maintains a registry of services, provides discovery, and exposes
    a health-dashboard view of the platform.
    """

    def __init__(self, load_defaults: bool = True) -> None:
        self._services: Dict[str, DeveloperService] = {}
        if load_defaults:
            self._seed_defaults()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register_service(
        self,
        name: str,
        description: str = "",
        tier: PortalTier = PortalTier.INTERNAL,
        version: str = "v1",
        api_base_url: Optional[str] = None,
        docs_url: Optional[str] = None,
        owner_team: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeveloperService:
        svc = DeveloperService(
            name=name,
            description=description,
            tier=tier,
            version=version,
            api_base_url=api_base_url,
            docs_url=docs_url,
            owner_team=owner_team,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._services[svc.service_id] = svc
        return svc

    def get_service(self, service_id: str) -> Optional[DeveloperService]:
        return self._services.get(service_id)

    def update_status(self, service_id: str, status: ServiceStatus) -> bool:
        svc = self._services.get(service_id)
        if svc is None:
            return False
        svc.status = status
        return True

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def list_services(
        self,
        tier: Optional[PortalTier] = None,
        tag: Optional[str] = None,
        status: Optional[ServiceStatus] = None,
    ) -> List[DeveloperService]:
        svcs = list(self._services.values())
        if tier:
            svcs = [s for s in svcs if s.tier == tier]
        if tag:
            svcs = [s for s in svcs if tag in s.tags]
        if status:
            svcs = [s for s in svcs if s.status == status]
        return svcs

    def search(self, query: str) -> List[DeveloperService]:
        q = query.lower()
        return [
            s
            for s in self._services.values()
            if q in s.name.lower()
            or q in s.description.lower()
            or any(q in tag for tag in s.tags)
        ]

    def health_dashboard(self) -> Dict[str, Any]:
        """Return a high-level health summary of all registered services."""
        counts: Dict[str, int] = {s.value: 0 for s in ServiceStatus}
        for svc in self._services.values():
            counts[svc.status.value] += 1
        return {
            "total_services": len(self._services),
            "status_counts": counts,
            "fully_operational": counts[ServiceStatus.OPERATIONAL.value] == len(self._services),
        }

    def total_count(self) -> int:
        return len(self._services)

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        for sd in _DEFAULT_SERVICES:
            self.register_service(**sd)
