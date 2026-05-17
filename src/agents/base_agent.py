"""Base agent module defining the abstract agent interface and shared data structures."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

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
    CODING = "coding"
    SUMMARIZATION = "summarization"


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
        llm: Optional[Any] = None,
        persist_memory: bool = False,
    ) -> None:
        self.config = config
        self.execution_agent = execution_agent
        self.llm = llm  # Optional LangChain chat model
        self.memory = AgentMemory(max_size=config.memory_size)
        self._tool_registry: Optional[Any] = None
        self._task_memory: Optional[Any] = None
        if persist_memory:
            try:
                from src.memory.task_memory import TaskMemory
                self._task_memory = TaskMemory(agent_name=config.name)
                logger.info("Persistent task memory enabled for '%s'", config.name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not initialise task memory: %s", exc)
        logger.info(
            "Initialised agent '%s' (type=%s, llm=%s)",
            config.name,
            config.agent_type,
            "enabled" if llm is not None else "mock",
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task and return a result dictionary."""

    async def stream_task(self, task: Dict[str, Any]) -> AsyncIterator[str]:
        """Stream task output as text chunks (default: yields full result as one chunk)."""
        import json
        result = await self.process_task(task)
        yield json.dumps(result)

    def get_status(self) -> Dict[str, Any]:
        """Return a status snapshot of this agent."""
        return {
            "name": self.config.name,
            "type": self.config.agent_type,
            "memory_usage": len(self.memory),
            "persistent_memory_size": len(self._task_memory) if self._task_memory else 0,
            "capabilities": self.config.capabilities,
        }

    def recall_similar_tasks(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Return past tasks semantically similar to *query* (requires persist_memory=True)."""
        if self._task_memory is None:
            return []
        return self._task_memory.recall(query, k=k)

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
        if self._task_memory is not None:
            try:
                self._task_memory.remember(task, result)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to persist task memory: %s", exc)

    async def _invoke_llm(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call the LLM and return the full response, or None if no LLM configured."""
        if self.llm is None:
            return None
        try:
            from src.llm.provider import invoke_llm
            return await invoke_llm(self.llm, system_prompt, user_prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM invocation failed: %s", exc)
            return None

    async def _stream_llm(self, prompt: str) -> AsyncIterator[str]:
        """Stream tokens from the LLM, or yield nothing if no LLM configured."""
        if self.llm is None:
            return
        try:
            from src.llm.provider import stream_llm_response
            async for chunk in stream_llm_response(self.llm, prompt):
                yield chunk
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM streaming failed: %s", exc)
