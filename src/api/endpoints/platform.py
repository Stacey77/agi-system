"""Platform endpoints — tooling landscape, developer portal, and Kally AI."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.agents.kally_agent import KallyAgent
from src.platform.developer_portal import DeveloperPortal, PortalTier
from src.platform.tool_landscape import ToolCategory, ToolLandscape, ToolTier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])

_EnumT = TypeVar("_EnumT", bound=Enum)


# ------------------------------------------------------------------
# Shared state / parsing helpers
# ------------------------------------------------------------------


def _get_tool_landscape(request: Request) -> ToolLandscape:
    landscape = getattr(request.app.state, "tool_landscape", None)
    if not isinstance(landscape, ToolLandscape):
        raise HTTPException(status_code=503, detail="Tool landscape not initialised")
    return landscape


def _get_developer_portal(request: Request) -> DeveloperPortal:
    portal = getattr(request.app.state, "developer_portal", None)
    if not isinstance(portal, DeveloperPortal):
        raise HTTPException(status_code=503, detail="Developer portal not initialised")
    return portal


def _get_kally_agent(request: Request) -> KallyAgent:
    agent = getattr(request.app.state, "kally_agent", None)
    if not isinstance(agent, KallyAgent):
        raise HTTPException(status_code=503, detail="Kally AI agent not initialised")
    return agent


def _parse_enum(enum_cls: Type[_EnumT], value: str, field_name: str) -> _EnumT:
    """Coerce ``value`` into ``enum_cls`` or raise a 400 with the valid options."""
    try:
        return enum_cls(value)
    except ValueError:
        valid = ", ".join(str(member.value) for member in enum_cls)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown {field_name} '{value}'. Valid values: {valid}",
        ) from None


# ------------------------------------------------------------------
# Response models
# ------------------------------------------------------------------


class ToolModel(BaseModel):
    tool_id: str
    name: str
    description: str
    category: str
    tier: str
    version: str
    homepage_url: Optional[str] = None
    docs_url: Optional[str] = None
    tags: List[str]
    owner_team: str
    is_active: bool


class ToolListResponse(BaseModel):
    tools: List[ToolModel]
    total: int


class ToolResponse(BaseModel):
    tool: ToolModel


class ToolsSummaryResponse(BaseModel):
    summary: Dict[str, int]
    total: int


class ServiceModel(BaseModel):
    service_id: str
    name: str
    description: str
    tier: str
    version: str
    api_base_url: Optional[str] = None
    docs_url: Optional[str] = None
    status: str
    owner_team: str
    tags: List[str]
    registered_at: str


class ServiceListResponse(BaseModel):
    services: List[ServiceModel]
    total: int


class ServiceResponse(BaseModel):
    service: ServiceModel


class PortalHealthResponse(BaseModel):
    total_services: int
    status_counts: Dict[str, int]
    fully_operational: bool


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


@router.get("/tools", response_model=ToolListResponse)
async def list_tools(
    request: Request,
    category: Optional[str] = None,
    tier: Optional[str] = None,
    tag: Optional[str] = None,
) -> ToolListResponse:
    """List platform tools from the tooling landscape."""
    landscape = _get_tool_landscape(request)
    cat_filter = _parse_enum(ToolCategory, category, "category") if category else None
    tier_filter = _parse_enum(ToolTier, tier, "tier") if tier else None
    tools = landscape.list_tools(category=cat_filter, tier=tier_filter, tag=tag)
    models = [ToolModel(**t.to_dict()) for t in tools]
    return ToolListResponse(tools=models, total=len(models))


@router.get("/tools/search", response_model=ToolListResponse)
async def search_tools(request: Request, q: str) -> ToolListResponse:
    """Search tools by name, description, or tags."""
    landscape = _get_tool_landscape(request)
    tools = landscape.search(q)
    models = [ToolModel(**t.to_dict()) for t in tools]
    return ToolListResponse(tools=models, total=len(models))


@router.get("/tools/summary", response_model=ToolsSummaryResponse)
async def tools_summary(request: Request) -> ToolsSummaryResponse:
    """Return tool counts per category."""
    landscape = _get_tool_landscape(request)
    return ToolsSummaryResponse(
        summary=landscape.categories_summary(),
        total=landscape.total_count(),
    )


@router.post("/tools", response_model=ToolResponse)
async def register_tool(body: RegisterToolRequest, request: Request) -> ToolResponse:
    """Register a new tool in the platform landscape."""
    landscape = _get_tool_landscape(request)
    cat = _parse_enum(ToolCategory, body.category, "category")
    tier = _parse_enum(ToolTier, body.tier, "tier")
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
    return ToolResponse(tool=ToolModel(**tool.to_dict()))


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


@router.get("/portal/services", response_model=ServiceListResponse)
async def list_services(
    request: Request,
    tier: Optional[str] = None,
    tag: Optional[str] = None,
) -> ServiceListResponse:
    """List services registered in the developer portal."""
    portal = _get_developer_portal(request)
    tier_filter = _parse_enum(PortalTier, tier, "tier") if tier else None
    services = portal.list_services(tier=tier_filter, tag=tag)
    models = [ServiceModel(**s.to_dict()) for s in services]
    return ServiceListResponse(services=models, total=len(models))


@router.get("/portal/services/search", response_model=ServiceListResponse)
async def search_services(request: Request, q: str) -> ServiceListResponse:
    """Search services by name, description, or tags."""
    portal = _get_developer_portal(request)
    services = portal.search(q)
    models = [ServiceModel(**s.to_dict()) for s in services]
    return ServiceListResponse(services=models, total=len(models))


@router.get("/portal/health", response_model=PortalHealthResponse)
async def portal_health(request: Request) -> PortalHealthResponse:
    """Return a health dashboard for all registered services."""
    portal = _get_developer_portal(request)
    return PortalHealthResponse(**portal.health_dashboard())


@router.post("/portal/services", response_model=ServiceResponse)
async def register_service(
    body: RegisterServiceRequest, request: Request
) -> ServiceResponse:
    """Register a new service in the developer portal."""
    portal = _get_developer_portal(request)
    tier = _parse_enum(PortalTier, body.tier, "tier")
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
    return ServiceResponse(service=ServiceModel(**svc.to_dict()))


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
    task: Dict[str, Any] = {
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
