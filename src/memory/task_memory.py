"""Task memory — persistent ChromaDB store for agent task history."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from src.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


class TaskMemory:
    """Stores and recalls task/result pairs using semantic similarity search."""

    def __init__(self, agent_name: str, persist_directory: Optional[str] = None) -> None:
        self._store = VectorStore(
            collection_name=f"tasks_{agent_name}",
            persist_directory=persist_directory,
        )

    def remember(self, task: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Persist a task+result pair; returns the generated memory ID."""
        memory_id = str(uuid.uuid4())
        document = (
            f"Task: {json.dumps(task, default=str)}\n"
            f"Result: {json.dumps(result, default=str)}"
        )
        self._store.add_documents(
            documents=[document],
            ids=[memory_id],
            metadatas=[{"agent": task.get("agent", ""), "status": result.get("status", "")}],
        )
        return memory_id

    def recall(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Return up to *k* past tasks semantically similar to *query*."""
        hits = self._store.similarity_search(query, k=k)
        results = []
        for hit in hits:
            try:
                doc = hit.get("document", "")
                task_part, _, result_part = doc.partition("\nResult: ")
                task_json = task_part.removeprefix("Task: ")
                results.append({
                    "id": hit.get("id"),
                    "task": json.loads(task_json) if task_json else {},
                    "result": json.loads(result_part) if result_part else {},
                    "metadata": hit.get("metadata", {}),
                })
            except (json.JSONDecodeError, ValueError):
                results.append({"id": hit.get("id"), "document": hit.get("document", "")})
        return results

    def __len__(self) -> int:
        return len(self._store)
