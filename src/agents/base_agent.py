"""Base agent module defining the abstract agent interface and shared data structures."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """Supported agent types."""

    PLANNING = "planning"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    WRITING = "writing"
    EXECUTION = "execution"
    REVIEW = "review"
    IDE = "ide"
    CDE = "cde"
    KALLY = "kally"


@dataclass
class AgentConfig:
    """Configuration for an agent instance."""

    name: str
    agent_type: AgentType
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    memory_size: int = 100
    tools: List[str] = field(default_factory=list)
    temperature: float = 0.7


@dataclass
class AgentMemory:
    """Per-agent short-term memory store."""

    max_size: int = 100
    _store: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, entry: Dict[str, Any]) -> None:
        """Add an entry, evicting oldest if at capacity."""
        if len(self._store) >= self.max_size:
            self._store.pop(0)
        self._store.append(entry)

    def get_all(self) -> List[Dict[str, Any]]:
        """Return all stored entries."""
        return list(self._store)

    def clear(self) -> None:
        """Clear memory."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


class BaseAgent(ABC):
    """Abstract base class for all AGI system agents."""

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.execution_agent = execution_agent
        self.memory = AgentMemory(max_size=config.memory_size)
        self._tool_registry: Optional[Any] = None
        logger.info("Initialised agent '%s' (type=%s)", config.name, config.agent_type)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task and return a result dictionary."""

    def get_status(self) -> Dict[str, Any]:
        """Return a status snapshot of this agent."""
        return {
            "name": self.config.name,
            "type": self.config.agent_type,
            "memory_usage": len(self.memory),
            "capabilities": self.config.capabilities,
        }

    def set_tool_registry(self, registry: Any) -> None:
        """Inject a tool registry for tool access."""
        self._tool_registry = registry

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_tool(self, name: str) -> Optional[Any]:
        if self._tool_registry is None:
            return None
        try:
            return self._tool_registry.get_tool(name)
        except Exception:  # noqa: BLE001
            return None

    def _record_task(self, task: Dict[str, Any], result: Dict[str, Any]) -> None:
        self.memory.add({"task": task, "result": result})
