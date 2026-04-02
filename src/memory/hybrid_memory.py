"""Hybrid memory — combines LangChain vector storage with CrewAI agent contexts."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


class HybridMemory:
    """Merges LangChain vector storage with per-agent CrewAI context stores.

    ``get_context(agent_id, query)`` returns a unified context that blends
    agent-specific episodic memory with broader semantic search results.
    """

    def __init__(self) -> None:
        self._shared_store = VectorStore(collection_name="hybrid_shared")
        self._agent_stores: Dict[str, VectorStore] = {}
        self._agent_contexts: Dict[str, List[Dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Context API
    # ------------------------------------------------------------------

    def get_context(self, agent_id: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Return a merged context for *agent_id* relevant to *query*."""
        shared_results = self._shared_store.similarity_search(query, k=k)
        agent_results = self._get_agent_results(agent_id, query, k=k)
        agent_context = self._agent_contexts.get(agent_id, [])

        # Deduplicate by document content
        seen: set = set()
        merged: List[Dict[str, Any]] = []
        for item in (agent_context + agent_results + shared_results):
            doc = item.get("document", str(item))
            if doc not in seen:
                seen.add(doc)
                merged.append(item)

        return merged[:k]

    def add_to_shared(
        self,
        documents: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add documents to the shared cross-agent store."""
        self._shared_store.add_documents(documents, ids=ids, metadatas=metadatas)

    def add_agent_context(
        self,
        agent_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a context entry specifically for *agent_id*."""
        if agent_id not in self._agent_stores:
            self._agent_stores[agent_id] = VectorStore(
                collection_name=f"agent_{agent_id}"
            )
        store = self._agent_stores[agent_id]
        doc_id = f"{agent_id}_{len(self._agent_contexts.get(agent_id, []))}"
        # ChromaDB requires non-empty metadata dicts; supply a sentinel if none provided.
        effective_metadata = metadata if metadata else {"_source": agent_id}
        store.add_documents([content], ids=[doc_id], metadatas=[effective_metadata])

        # Also keep a lightweight in-memory cache
        if agent_id not in self._agent_contexts:
            self._agent_contexts[agent_id] = []
        self._agent_contexts[agent_id].append(
            {"document": content, "metadata": metadata or {}}
        )
        logger.debug("HybridMemory: added context for agent '%s'", agent_id)

    def clear_agent_context(self, agent_id: str) -> None:
        """Remove all context for *agent_id*."""
        self._agent_contexts.pop(agent_id, None)
        if agent_id in self._agent_stores:
            del self._agent_stores[agent_id]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_agent_results(
        self, agent_id: str, query: str, k: int
    ) -> List[Dict[str, Any]]:
        store = self._agent_stores.get(agent_id)
        if store is None:
            return []
        return store.similarity_search(query, k=k)
