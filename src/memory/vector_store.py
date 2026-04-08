"""Vector store — semantic similarity search interface (ChromaDB integration)."""

from __future__ import annotations

import hashlib
import logging
import struct
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class _OfflineEmbeddingFunction:
    """Hash-based embedding function that requires no network access or model downloads."""

    _DIM = 64  # fixed embedding dimension

    def name(self) -> str:  # noqa: D401
        return "offline_hash"

    def embed_query(self, input: List[str]) -> List[List[float]]:  # noqa: A001
        return self(input)

    def __call__(self, input: List[str]) -> List[List[float]]:  # noqa: A001
        embeddings: List[List[float]] = []
        for text in input:
            floats: List[float] = []
            seed = text.encode()
            chunk = 0
            while len(floats) < self._DIM:
                digest = hashlib.sha256(seed + struct.pack("I", chunk)).digest()
                for i in range(0, len(digest) - 3, 4):
                    floats.append(struct.unpack("f", digest[i : i + 4])[0])
                    if len(floats) == self._DIM:
                        break
                chunk += 1
            embeddings.append(floats[: self._DIM])
        return embeddings


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

            ef = _OfflineEmbeddingFunction()
            if self._persist_directory:
                self._client = chromadb.PersistentClient(path=self._persist_directory)
            else:
                self._client = chromadb.EphemeralClient()
            self._collection = self._client.get_or_create_collection(
                self._collection_name,
                embedding_function=ef,  # type: ignore[arg-type]
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
        # ChromaDB requires every metadata dict to be non-empty.
        normalized = [m or {"_type": "document"} for m in (metadatas or [{} for _ in documents])]
        self._collection.add(  # type: ignore[union-attr]
            documents=documents,
            ids=ids,
            metadatas=normalized,
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
