"""Vector store — semantic similarity search interface (ChromaDB integration)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VectorStore:
    """Semantic vector store backed by ChromaDB (or an in-memory mock fallback)."""

    def __init__(
        self,
        collection_name: str = "agi_memory",
        persist_directory: Optional[str] = None,
    ) -> None:
        self._collection_name = collection_name
        self._persist_directory = persist_directory
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._mock_store: List[Dict[str, Any]] = []
        self._use_mock = False
        self._init_client()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_client(self) -> None:
        try:
            import chromadb  # type: ignore[import]

            if self._persist_directory:
                self._client = chromadb.PersistentClient(path=self._persist_directory)
            else:
                self._client = chromadb.Client()
            self._collection = self._client.get_or_create_collection(
                self._collection_name
            )
            logger.info("VectorStore: ChromaDB collection '%s' ready", self._collection_name)
        except ImportError:
            logger.warning("chromadb not installed; using in-memory mock vector store")
            self._use_mock = True

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_documents(
        self,
        documents: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add *documents* to the store."""
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        if self._use_mock:
            for i, doc in enumerate(documents):
                self._mock_store.append(
                    {
                        "id": ids[i],
                        "document": doc,
                        "metadata": (metadatas or [{}])[i] if metadatas else {},
                    }
                )
            return
        self._collection.add(  # type: ignore[union-attr]
            documents=documents,
            ids=ids,
            metadatas=metadatas or [{} for _ in documents],
        )
        logger.debug("VectorStore: added %d documents", len(documents))

    def similarity_search(
        self, query: str, k: int = 5
    ) -> List[Dict[str, Any]]:
        """Return the *k* most similar documents to *query*."""
        if self._use_mock:
            # Simple substring mock similarity
            scored = [
                (entry, sum(1 for w in query.lower().split() if w in entry["document"].lower()))
                for entry in self._mock_store
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [e for e, _ in scored[:k]]

        results = self._collection.query(  # type: ignore[union-attr]
            query_texts=[query], n_results=min(k, max(1, len(self._mock_store or [1])))
        )
        docs = results.get("documents", [[]])[0]
        meta = results.get("metadatas", [[]])[0]
        ids = results.get("ids", [[]])[0]
        return [
            {"id": ids[i], "document": docs[i], "metadata": meta[i]}
            for i in range(len(docs))
        ]

    def delete(self, ids: List[str]) -> None:
        """Delete documents by *ids*."""
        if self._use_mock:
            self._mock_store = [e for e in self._mock_store if e["id"] not in ids]
            return
        self._collection.delete(ids=ids)  # type: ignore[union-attr]
        logger.debug("VectorStore: deleted %d documents", len(ids))

    def __len__(self) -> int:
        if self._use_mock:
            return len(self._mock_store)
        return self._collection.count()  # type: ignore[union-attr]
