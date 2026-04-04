"""Platform endpoints — tooling landscape, developer portal, and Kally AI."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.platform.developer_portal import DeveloperPortal, PortalTier, ServiceStatus
from src.platform.tool_landscape import ToolCategory, ToolLandscape, ToolTier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


# ------------------------------------------------------------------
# Shared state helpers
# ------------------------------------------------------------------

def _get_tool_landscape(request: Request) -> ToolLandscape:
    landscape = getattr(request.app.state, "tool_landscape", None)
    if landscape is None:
        raise HTTPException(status_code=503, detail="Tool landscape not initialised")
    return landscape


def _get_developer_portal(request: Request) -> DeveloperPortal:
    portal = getattr(request.app.state, "developer_portal", None)
    if portal is None:
        raise HTTPException(status_code=503, detail="Developer portal not initialised")
    return portal


def _get_kally_agent(request: Request) -> Any:
    agent = getattr(request.app.state, "kally_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="Kally AI agent not initialised")
    return agent


# ------------------------------------------------------------------
# Platform tooling landscape
# ------------------------------------------------------------------

class RegisterToolRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "other"
    tier: str = "both"
    version: str = "latest"
    homepage_url: Optional[str] = None
    docs_url: Optional[str] = None
    tags: List[str] = []
    owner_team: str = ""


@router.get("/tools")
async def list_tools(
    request: Request,
    category: Optional[str] = None,
    tier: Optional[str] = None,
    tag: Optional[str] = None,
) -> Dict[str, Any]:
    """List platform tools from the tooling landscape."""
    landscape = _get_tool_landscape(request)
    cat_filter: Optional[ToolCategory] = None
    tier_filter: Optional[ToolTier] = None
    if category:
        try:
            cat_filter = ToolCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown category '{category}'")
    if tier:
        try:
            tier_filter = ToolTier(tier)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown tier '{tier}'")
    tools = landscape.list_tools(category=cat_filter, tier=tier_filter, tag=tag)
    return {"tools": [t.to_dict() for t in tools], "total": len(tools)}


@router.get("/tools/search")
async def search_tools(request: Request, q: str) -> Dict[str, Any]:
    """Search tools by name, description, or tags."""
    landscape = _get_tool_landscape(request)
    tools = landscape.search(q)
    return {"tools": [t.to_dict() for t in tools], "total": len(tools)}


@router.get("/tools/summary")
async def tools_summary(request: Request) -> Dict[str, Any]:
    """Return tool counts per category."""
    landscape = _get_tool_landscape(request)
    return {"summary": landscape.categories_summary(), "total": landscape.total_count()}


@router.post("/tools")
async def register_tool(body: RegisterToolRequest, request: Request) -> Dict[str, Any]:
    """Register a new tool in the platform landscape."""
    landscape = _get_tool_landscape(request)
    try:
        cat = ToolCategory(body.category)
    except ValueError:
        cat = ToolCategory.OTHER
    try:
        tier = ToolTier(body.tier)
    except ValueError:
        tier = ToolTier.BOTH
    tool = landscape.register_tool(
        name=body.name,
        description=body.description,
        category=cat,
        tier=tier,
        version=body.version,
        homepage_url=body.homepage_url,
        docs_url=body.docs_url,
        tags=body.tags,
        owner_team=body.owner_team,
    )
    return {"tool": tool.to_dict()}


# ------------------------------------------------------------------
# Developer portal
# ------------------------------------------------------------------

class RegisterServiceRequest(BaseModel):
    name: str
    description: str = ""
    tier: str = "internal"
    version: str = "v1"
    api_base_url: Optional[str] = None
    docs_url: Optional[str] = None
    owner_team: str = ""
    tags: List[str] = []


@router.get("/portal/services")
async def list_services(
    request: Request,
    tier: Optional[str] = None,
    tag: Optional[str] = None,
) -> Dict[str, Any]:
    """List services registered in the developer portal."""
    portal = _get_developer_portal(request)
    tier_filter: Optional[PortalTier] = None
    if tier:
        try:
            tier_filter = PortalTier(tier)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown tier '{tier}'")
    services = portal.list_services(tier=tier_filter, tag=tag)
    return {"services": [s.to_dict() for s in services], "total": len(services)}


@router.get("/portal/services/search")
async def search_services(request: Request, q: str) -> Dict[str, Any]:
    """Search services by name, description, or tags."""
    portal = _get_developer_portal(request)
    services = portal.search(q)
    return {"services": [s.to_dict() for s in services], "total": len(services)}


@router.get("/portal/health")
async def portal_health(request: Request) -> Dict[str, Any]:
    """Return a health dashboard for all registered services."""
    portal = _get_developer_portal(request)
    return portal.health_dashboard()


@router.post("/portal/services")
async def register_service(body: RegisterServiceRequest, request: Request) -> Dict[str, Any]:
    """Register a new service in the developer portal."""
    portal = _get_developer_portal(request)
    try:
        tier = PortalTier(body.tier)
    except ValueError:
        tier = PortalTier.INTERNAL
    svc = portal.register_service(
        name=body.name,
        description=body.description,
        tier=tier,
        version=body.version,
        api_base_url=body.api_base_url,
        docs_url=body.docs_url,
        owner_team=body.owner_team,
        tags=body.tags,
    )
    return {"service": svc.to_dict()}


# ------------------------------------------------------------------
# Kally AI
# ------------------------------------------------------------------

class KallySignalRequest(BaseModel):
    source: str
    metric: str
    value: float
    threshold: float = 0.0
    severity: str = "info"
    metadata: Dict[str, Any] = {}


class KallyActionRequest(BaseModel):
    action: str = "analyse"
    parameters: Dict[str, Any] = {}


@router.post("/kally/signals")
async def ingest_signal(body: KallySignalRequest, request: Request) -> Dict[str, Any]:
    """Ingest a feedback signal into the Kally closed-loop system."""
    kally = _get_kally_agent(request)
    task = {
        "action": "ingest",
        "source": body.source,
        "metric": body.metric,
        "value": body.value,
        "threshold": body.threshold,
        "severity": body.severity,
        "metadata": body.metadata,
    }
    return await kally.process_task(task)


@router.post("/kally/analyse")
async def kally_analyse(request: Request) -> Dict[str, Any]:
    """Trigger a Kally closed-loop analysis cycle."""
    kally = _get_kally_agent(request)
    return await kally.process_task({"action": "analyse"})


@router.get("/kally/report")
async def kally_report(request: Request) -> Dict[str, Any]:
    """Get the current Kally health report."""
    kally = _get_kally_agent(request)
    return await kally.process_task({"action": "report"})


@router.post("/kally/reset")
async def kally_reset(request: Request) -> Dict[str, Any]:
    """Reset the Kally signal buffer and action log."""
    kally = _get_kally_agent(request)
    return await kally.process_task({"action": "reset"})
