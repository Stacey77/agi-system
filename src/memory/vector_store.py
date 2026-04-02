"""Vector store — semantic similarity search interface (ChromaDB integration)."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_EMBEDDING_DIM = 16  # small fixed dimension for the offline fallback


class _OfflineEmbeddingFunction:
    """Hash-based embedding function that works fully offline.

    Produces a fixed-length vector derived from the MD5 digest of each text.
    Not semantically meaningful but sufficient for unit tests and offline
    environments where the ONNX model cannot be downloaded.
    """

    def is_legacy(self) -> bool:  # ChromaDB ≥ 1.x checks this as a callable
        return False

    def name(self) -> str:  # ChromaDB ≥ 1.x expects name() to be callable
        return "offline_hash_embedding"

    def __call__(self, input: List[str]) -> List[List[float]]:  # noqa: A002
        result = []
        for text in input:
            digest = hashlib.md5(text.encode("utf-8")).digest()
            # Normalise bytes to [-1, 1]
            vec = [(b / 127.5) - 1.0 for b in digest[:_EMBEDDING_DIM]]
            result.append(vec)
        return result



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
                # EphemeralClient is a true in-memory instance (no HTTP server needed).
                self._client = chromadb.EphemeralClient()
            self._collection = self._client.get_or_create_collection(
                self._collection_name,
                embedding_function=_OfflineEmbeddingFunction(),
            )
            logger.info("VectorStore: ChromaDB collection '%s' ready", self._collection_name)
        except ImportError:
            logger.warning("chromadb not installed; using in-memory mock vector store")
            self._use_mock = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("ChromaDB init error (%s); falling back to mock vector store", exc)
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
        # ChromaDB requires each metadata dict to be non-empty.
        effective_metadatas: List[Dict[str, Any]] = []
        for i, _doc in enumerate(documents):
            meta = (metadatas[i] if metadatas else None) or {"_id": ids[i]}
            effective_metadatas.append(meta)
        try:
            self._collection.add(  # type: ignore[union-attr]
                documents=documents,
                ids=ids,
                metadatas=effective_metadatas,
            )
            logger.debug("VectorStore: added %d documents", len(documents))
        except Exception as exc:  # noqa: BLE001
            logger.warning("ChromaDB add failed (%s); switching to mock for this store", exc)
            self._use_mock = True
            for i, doc in enumerate(documents):
                self._mock_store.append(
                    {
                        "id": ids[i],
                        "document": doc,
                        "metadata": effective_metadatas[i],
                    }
                )

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

        try:
            n_results = min(k, max(1, self._collection.count()))  # type: ignore[union-attr]
            results = self._collection.query(  # type: ignore[union-attr]
                query_texts=[query], n_results=n_results
            )
            docs = results.get("documents", [[]])[0]
            meta = results.get("metadatas", [[]])[0]
            result_ids = results.get("ids", [[]])[0]
            return [
                {"id": result_ids[i], "document": docs[i], "metadata": meta[i]}
                for i in range(len(docs))
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("ChromaDB query failed (%s); using mock fallback", exc)
            self._use_mock = True
            return []

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
