"""Platform tooling landscape — catalog and discovery of platform tools."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ToolCategory(str, Enum):
    """High-level categories for platform tools."""

    CI_CD = "ci_cd"
    OBSERVABILITY = "observability"
    SECURITY = "security"
    DATA = "data"
    AI_ML = "ai_ml"
    INFRASTRUCTURE = "infrastructure"
    COLLABORATION = "collaboration"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    OTHER = "other"


class ToolTier(str, Enum):
    """Audience tier for a platform tool."""

    INTERNAL = "internal"
    EXTERNAL = "external"
    BOTH = "both"


@dataclass
class PlatformTool:
    """Metadata record for a platform tool."""

    tool_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.OTHER
    tier: ToolTier = ToolTier.BOTH
    version: str = "latest"
    homepage_url: Optional[str] = None
    docs_url: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    owner_team: str = ""
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tier": self.tier,
            "version": self.version,
            "homepage_url": self.homepage_url,
            "docs_url": self.docs_url,
            "tags": self.tags,
            "owner_team": self.owner_team,
            "is_active": self.is_active,
        }


# Built-in default tools that ship with the platform
_DEFAULT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "GitHub Actions",
        "description": "CI/CD automation platform",
        "category": ToolCategory.CI_CD,
        "tier": ToolTier.BOTH,
        "homepage_url": "https://github.com/features/actions",
        "tags": ["ci", "cd", "automation"],
        "owner_team": "platform",
    },
    {
        "name": "Prometheus",
        "description": "Metrics collection and alerting",
        "category": ToolCategory.OBSERVABILITY,
        "tier": ToolTier.INTERNAL,
        "tags": ["metrics", "alerting", "monitoring"],
        "owner_team": "platform",
    },
    {
        "name": "Grafana",
        "description": "Observability dashboards",
        "category": ToolCategory.OBSERVABILITY,
        "tier": ToolTier.INTERNAL,
        "tags": ["dashboards", "visualisation"],
        "owner_team": "platform",
    },
    {
        "name": "Trivy",
        "description": "Container and filesystem vulnerability scanner",
        "category": ToolCategory.SECURITY,
        "tier": ToolTier.BOTH,
        "tags": ["security", "scanning", "container"],
        "owner_team": "security",
    },
    {
        "name": "ArgoCD",
        "description": "GitOps continuous delivery for Kubernetes",
        "category": ToolCategory.CI_CD,
        "tier": ToolTier.INTERNAL,
        "tags": ["gitops", "kubernetes", "cd"],
        "owner_team": "platform",
    },
    {
        "name": "ChromaDB",
        "description": "Embedded vector database for AI workloads",
        "category": ToolCategory.AI_ML,
        "tier": ToolTier.BOTH,
        "tags": ["vector-db", "ai", "embeddings"],
        "owner_team": "ai",
    },
    {
        "name": "Terraform",
        "description": "Infrastructure-as-code provisioning",
        "category": ToolCategory.INFRASTRUCTURE,
        "tier": ToolTier.INTERNAL,
        "tags": ["iac", "provisioning"],
        "owner_team": "infra",
    },
    {
        "name": "Kally AI",
        "description": "Closed-loop AI system for continuous platform improvement",
        "category": ToolCategory.AI_ML,
        "tier": ToolTier.INTERNAL,
        "tags": ["ai", "closed-loop", "feedback"],
        "owner_team": "ai",
    },
]


class ToolLandscape:
    """Registry and discovery service for platform tools."""

    def __init__(self, load_defaults: bool = True) -> None:
        self._tools: Dict[str, PlatformTool] = {}
        if load_defaults:
            self._seed_defaults()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str = "",
        category: ToolCategory = ToolCategory.OTHER,
        tier: ToolTier = ToolTier.BOTH,
        version: str = "latest",
        homepage_url: Optional[str] = None,
        docs_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
        owner_team: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PlatformTool:
        tool = PlatformTool(
            name=name,
            description=description,
            category=category,
            tier=tier,
            version=version,
            homepage_url=homepage_url,
            docs_url=docs_url,
            tags=tags or [],
            owner_team=owner_team,
            metadata=metadata or {},
        )
        self._tools[tool.tool_id] = tool
        return tool

    def get_tool(self, tool_id: str) -> Optional[PlatformTool]:
        return self._tools.get(tool_id)

    def deactivate_tool(self, tool_id: str) -> bool:
        tool = self._tools.get(tool_id)
        if tool is None:
            return False
        tool.is_active = False
        return True

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        tier: Optional[ToolTier] = None,
        tag: Optional[str] = None,
        active_only: bool = True,
    ) -> List[PlatformTool]:
        tools = list(self._tools.values())
        if active_only:
            tools = [t for t in tools if t.is_active]
        if category:
            tools = [t for t in tools if t.category == category]
        if tier:
            tools = [t for t in tools if t.tier in (tier, ToolTier.BOTH)]
        if tag:
            tools = [t for t in tools if tag in t.tags]
        return tools

    def search(self, query: str) -> List[PlatformTool]:
        """Simple substring search across name, description, and tags."""
        q = query.lower()
        return [
            t
            for t in self._tools.values()
            if t.is_active
            and (
                q in t.name.lower()
                or q in t.description.lower()
                or any(q in tag for tag in t.tags)
            )
        ]

    def categories_summary(self) -> Dict[str, int]:
        """Return tool count per category."""
        summary: Dict[str, int] = {}
        for tool in self._tools.values():
            if tool.is_active:
                key = tool.category.value
                summary[key] = summary.get(key, 0) + 1
        return summary

    def total_count(self) -> int:
        return len(self._tools)

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        for td in _DEFAULT_TOOLS:
            self.register_tool(**td)
