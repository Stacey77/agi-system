"""High-level workforce manager."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.workforce.task_dispatcher import TaskDispatcher
from src.workforce.worker_pool import WorkerPool

logger = logging.getLogger(__name__)


class WorkforceManager:
    """Manages the autonomous intelligent workforce."""

    def __init__(
        self,
        agent_factory: Any | None = None,
        task_queue: Any | None = None,
    ) -> None:
        self._factory = agent_factory
        self._queue = task_queue
        self._pool = WorkerPool()
        self._dispatcher = TaskDispatcher(self._pool, task_queue)

    async def initialize_from_factory(self) -> None:
        if self._factory is None:
            return
        list_agents = getattr(self._factory, "list_agents", None)
        if list_agents is None:
            return
        agents = list_agents()
        for agent in agents:
            cfg = getattr(agent, "config", None)
            if cfg is None:
                continue
            name = getattr(cfg, "name", None) or getattr(agent, "name", "unknown")
            agent_type = getattr(cfg, "agent_type", None)
            agent_type_val = (
                agent_type.value if hasattr(agent_type, "value") else str(agent_type)
            )
            caps = list(getattr(cfg, "capabilities", []) or [])
            self._pool.add_worker(name=name, agent_type=agent_type_val, skills=caps)

    async def hire(
        self, name: str, agent_type: str, skills: list[str]
    ) -> dict[str, Any]:
        worker = self._pool.add_worker(name=name, agent_type=agent_type, skills=skills)
        return worker.to_dict()

    async def fire(self, worker_id: str) -> bool:
        return self._pool.remove_worker(worker_id)

    async def assign_objective(
        self,
        objective: str,
        required_skills: list[str] | None = None,
    ) -> dict[str, Any]:
        result = await self._dispatcher.dispatch(
            objective, required_skills=required_skills
        )
        if result.get("status") == "assigned" and result.get("worker_id"):
            asyncio.create_task(
                self._execute_via_agent(
                    objective=objective,
                    task_id=result["task_id"],
                    worker_id=result["worker_id"],
                )
            )
        return result

    async def _execute_via_agent(
        self, objective: str, task_id: str, worker_id: str
    ) -> None:
        worker = self._pool.get_worker(worker_id)
        if worker is None or self._factory is None:
            self._pool.complete_task(worker_id, success=False)
            return
        agent_name = f"{worker.agent_type}_agent"
        get_agent = getattr(self._factory, "get_agent", None)
        agent = get_agent(agent_name) if get_agent else None
        if agent is None:
            # No matching agent — mark complete gracefully.
            self._pool.complete_task(worker_id, success=True)
            return
        try:
            await agent.process_task({"objective": objective, "task_id": task_id})
            self._pool.complete_task(worker_id, success=True)
        except Exception:
            logger.exception("Agent %s failed executing task %s", agent_name, task_id)
            self._pool.complete_task(worker_id, success=False)

    async def assign_batch(
        self, objectives: list[str], required_skills: list[str] | None = None
    ) -> list[dict[str, Any]]:
        return await self._dispatcher.dispatch_batch(
            objectives, required_skills=required_skills
        )

    def workforce_status(self) -> dict[str, Any]:
        stats = self._pool.stats()
        workers = [w.to_dict() for w in self._pool.list_workers()]
        return {**stats, "workers": workers}

    async def scale_up(self, agent_type: str, count: int = 1) -> list[dict[str, Any]]:
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
