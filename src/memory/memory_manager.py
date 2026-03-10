"""Memory manager — coordinates short-term, long-term, and episodic memory."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.memory.conversation_memory import ConversationMemory
from src.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)

_MEMORY_TYPES = frozenset({"short_term", "long_term", "episodic"})


class MemoryManager:
    """Central coordinator for all memory subsystems."""

    def __init__(self) -> None:
        self._short_term: Dict[str, Any] = {}
        self._long_term = VectorStore(collection_name="long_term")
        self._episodic = VectorStore(collection_name="episodic")
        self._conversation = ConversationMemory()

    # ------------------------------------------------------------------
    # Store / retrieve / search
    # ------------------------------------------------------------------

    def store(self, key: str, value: Any, memory_type: str = "short_term") -> None:
        """Store *value* under *key* in the specified *memory_type*."""
        self._validate_type(memory_type)
        if memory_type == "short_term":
            self._short_term[key] = value
        elif memory_type == "long_term":
            self._long_term.add_documents([str(value)], ids=[key])
        elif memory_type == "episodic":
            self._episodic.add_documents([str(value)], ids=[key])
        logger.debug("MemoryManager.store: key='%s' type='%s'", key, memory_type)

    def retrieve(self, key: str, memory_type: str = "short_term") -> Optional[Any]:
        """Retrieve value for *key* from *memory_type*."""
        self._validate_type(memory_type)
        if memory_type == "short_term":
            return self._short_term.get(key)
        store = self._long_term if memory_type == "long_term" else self._episodic
        results = store.similarity_search(key, k=1)
        return results[0] if results else None

    def search(self, query: str, memory_type: str = "long_term") -> List[Any]:
        """Semantic search across *memory_type* store."""
        self._validate_type(memory_type)
        if memory_type == "short_term":
            return [
                v for k, v in self._short_term.items()
                if query.lower() in str(k).lower() or query.lower() in str(v).lower()
            ]
        store = self._long_term if memory_type == "long_term" else self._episodic
        return store.similarity_search(query, k=5)

    # ------------------------------------------------------------------
    # Conversation shortcuts
    # ------------------------------------------------------------------

    def add_conversation_message(self, role: str, content: str) -> None:
        self._conversation.add_message(role, content)

    def get_conversation_context(self, n: int = 5) -> List[Any]:
        return self._conversation.get_recent_context(n)

    def clear_conversation(self) -> None:
        self._conversation.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_type(self, memory_type: str) -> None:
        if memory_type not in _MEMORY_TYPES:
            raise ValueError(
                f"Unknown memory_type '{memory_type}'. "
                f"Must be one of: {sorted(_MEMORY_TYPES)}"
            )
