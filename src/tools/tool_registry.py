"""Tool registry — centralised lookup and categorisation of tools."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from src.tools.base_tool import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """Register *tool* by its metadata name."""
        name = tool.metadata.name
        if name in self._tools:
            logger.warning("Tool '%s' is already registered; overwriting", name)
        self._tools[name] = tool
        logger.info("Registered tool '%s' (category=%s)", name, tool.metadata.category)

    def get_tool(self, name: str) -> BaseTool:
        """Return the tool with *name*, raising KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"No tool registered with name: '{name}'")
        return self._tools[name]

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """Return all tools belonging to *category*."""
        return [t for t in self._tools.values() if t.metadata.category == category]

    def list_tools(self) -> List[ToolMetadata]:
        """Return metadata for all registered tools."""
        return [t.metadata for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
