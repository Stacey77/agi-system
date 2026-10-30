"""Task dispatcher — routes objectives to available workers."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from src.workforce.worker_pool import WorkerPool


class TaskDispatcher:
    """Dispatches tasks from a queue to workers in the pool."""

    def __init__(self, worker_pool: WorkerPool, task_queue: Optional[Any] = None) -> None:
        self._pool = worker_pool
        self._queue = task_queue
        self._assignments: Dict[str, Dict[str, Any]] = {}

    async def dispatch(
        self,
        objective: str,
        required_skills: Optional[List[str]] = None,
        priority: int = 0,
    ) -> Dict[str, Any]:
        worker = self._pool.find_available(required_skills)
        task_id: Optional[str] = None

        if self._queue is not None:
            try:
                record = await self._queue.submit(objective, {"priority": priority})
                task_id = record.task_id
            except Exception:
                task_id = None

        if task_id is None:
            import uuid
            task_id = str(uuid.uuid4())

        status = "queued"
        worker_id: Optional[str] = None
        worker_name: Optional[str] = None

        if worker is not None:
            if self._pool.assign_task(worker.worker_id, task_id):
                worker_id = worker.worker_id
                worker_name = worker.name
                status = "assigned"

        self._assignments[task_id] = {
            "task_id": task_id,
            "worker_id": worker_id,
            "assigned_at": time.time(),
        }

        return {
            "task_id": task_id,
            "worker_id": worker_id,
            "worker_name": worker_name,
            "status": status,
            "objective": objective,
        }

    async def dispatch_batch(
        self,
        objectives: List[str],
        required_skills: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for obj in objectives:
            results.append(await self.dispatch(obj, required_skills=required_skills))
        return results

    async def rebalance(self) -> Dict[str, Any]:
        # In a full implementation this would move tasks between workers.
        # Here we simply report how many workers are busy.
        busy = self._pool.list_workers(status="busy")
        return {"reassigned": 0, "busy_workers": len(busy)}

    def get_assignment(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._assignments.get(task_id)

    def __repr__(self) -> str:
        return f"TaskDispatcher(assignments={len(self._assignments)}, pool={self._pool!r})"
