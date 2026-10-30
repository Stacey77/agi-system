"""High-level workforce manager."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.workforce.worker_pool import WorkerPool
from src.workforce.task_dispatcher import TaskDispatcher


class WorkforceManager:
    """Manages the autonomous intelligent workforce."""

    def __init__(
        self,
        agent_factory: Optional[Any] = None,
        task_queue: Optional[Any] = None,
    ) -> None:
        self._factory = agent_factory
        self._queue = task_queue
        self._pool = WorkerPool()
        self._dispatcher = TaskDispatcher(self._pool, task_queue)

    async def initialize_from_factory(self) -> None:
        if self._factory is None:
            return
        try:
            agents = self._factory.list_agents()
        except Exception:
            return
        for agent in agents:
            cfg = getattr(agent, "config", None)
            if cfg is None:
                continue
            name = getattr(cfg, "name", None) or getattr(agent, "name", "unknown")
            agent_type = getattr(cfg, "agent_type", None)
            agent_type_val = agent_type.value if hasattr(agent_type, "value") else str(agent_type)
            caps = list(getattr(cfg, "capabilities", []) or [])
            self._pool.add_worker(name=name, agent_type=agent_type_val, skills=caps)

    async def hire(
        self, name: str, agent_type: str, skills: List[str]
    ) -> Dict[str, Any]:
        worker = self._pool.add_worker(name=name, agent_type=agent_type, skills=skills)
        return worker.to_dict()

    async def fire(self, worker_id: str) -> bool:
        return self._pool.remove_worker(worker_id)

    async def assign_objective(
        self,
        objective: str,
        required_skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await self._dispatcher.dispatch(objective, required_skills=required_skills)

    async def assign_batch(
        self, objectives: List[str], required_skills: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        return await self._dispatcher.dispatch_batch(objectives, required_skills=required_skills)

    def workforce_status(self) -> Dict[str, Any]:
        stats = self._pool.stats()
        workers = [w.to_dict() for w in self._pool.list_workers()]
        return {**stats, "workers": workers}

    async def scale_up(self, agent_type: str, count: int = 1) -> List[Dict[str, Any]]:
        results = []
        for i in range(count):
            worker = self._pool.add_worker(
                name=f"{agent_type}_{i + 1}",
                agent_type=agent_type,
                skills=[agent_type],
            )
            results.append(worker.to_dict())
        return results

    def __repr__(self) -> str:
        stats = self._pool.stats()
        return f"WorkforceManager(workers={stats['total']}, idle={stats['idle']}, busy={stats['busy']})"
