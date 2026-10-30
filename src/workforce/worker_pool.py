"""Worker pool for the autonomous intelligent workforce."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Worker:
    worker_id: str
    name: str
    agent_type: str
    skills: List[str]
    status: str = "idle"
    current_task_id: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "worker_id": self.worker_id,
            "name": self.name,
            "agent_type": self.agent_type,
            "skills": self.skills,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return f"Worker(id={self.worker_id[:8]}, name={self.name!r}, status={self.status!r})"


class WorkerPool:
    """Thread-safe in-memory pool of workers."""

    def __init__(self) -> None:
        self._workers: Dict[str, Worker] = {}

    def add_worker(self, name: str, agent_type: str, skills: List[str]) -> Worker:
        worker = Worker(
            worker_id=str(uuid.uuid4()),
            name=name,
            agent_type=agent_type,
            skills=list(skills),
        )
        self._workers[worker.worker_id] = worker
        return worker

    def remove_worker(self, worker_id: str) -> bool:
        if worker_id in self._workers:
            del self._workers[worker_id]
            return True
        return False

    def get_worker(self, worker_id: str) -> Optional[Worker]:
        return self._workers.get(worker_id)

    def list_workers(
        self,
        status: Optional[str] = None,
        skill: Optional[str] = None,
    ) -> List[Worker]:
        workers = list(self._workers.values())
        if status:
            workers = [w for w in workers if w.status == status]
        if skill:
            workers = [w for w in workers if skill in w.skills]
        return workers

    def assign_task(self, worker_id: str, task_id: str) -> bool:
        w = self._workers.get(worker_id)
        if w is None or w.status != "idle":
            return False
        w.status = "busy"
        w.current_task_id = task_id
        return True

    def complete_task(self, worker_id: str, success: bool = True) -> None:
        w = self._workers.get(worker_id)
        if w is None:
            return
        w.status = "idle"
        w.current_task_id = None
        if success:
            w.tasks_completed += 1
        else:
            w.tasks_failed += 1

    def find_available(self, required_skills: Optional[List[str]] = None) -> Optional[Worker]:
        for w in self._workers.values():
            if w.status != "idle":
                continue
            if required_skills:
                if all(s in w.skills for s in required_skills):
                    return w
            else:
                return w
        return None

    def stats(self) -> Dict:
        workers = list(self._workers.values())
        idle = sum(1 for w in workers if w.status == "idle")
        busy = sum(1 for w in workers if w.status == "busy")
        offline = sum(1 for w in workers if w.status == "offline")
        total_completed = sum(w.tasks_completed for w in workers)
        total_failed = sum(w.tasks_failed for w in workers)
        return {
            "total": len(workers),
            "idle": idle,
            "busy": busy,
            "offline": offline,
            "tasks_completed": total_completed,
            "tasks_failed": total_failed,
        }

    def __repr__(self) -> str:
        s = self.stats()
        return f"WorkerPool(total={s['total']}, idle={s['idle']}, busy={s['busy']})"
