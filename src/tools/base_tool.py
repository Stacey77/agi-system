"""Base tool — abstract interface and metadata definition."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """Metadata describing a tool."""

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    return_type: str = "Any"
    category: str = "general"
    required_permissions: List[str] = field(default_factory=list)


class BaseTool(ABC):
    """Abstract base class for all AGI system tools."""

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Return tool metadata."""

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the given keyword arguments."""

    def validate_parameters(self, **kwargs: Any) -> bool:
        """Check that all required parameters are present."""
        required = self.metadata.parameters.get("required", [])
        missing = [p for p in required if p not in kwargs]
        if missing:
            logger.warning("Tool '%s' missing parameters: %s", self.metadata.name, missing)
            return False
        return True

    def __str__(self) -> str:
        return f"Tool({self.metadata.name})"

    def __repr__(self) -> str:
        return f"<BaseTool name={self.metadata.name!r} category={self.metadata.category!r}>"
