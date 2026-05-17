"""Simple asyncio-based task scheduler for recurring submissions."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    schedule_id: str
    objective: str
    parameters: Dict[str, Any]
    interval_seconds: float
    next_run_at: float
    enabled: bool = True
    run_count: int = 0
    last_task_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "objective": self.objective,
            "parameters": self.parameters,
            "interval_seconds": self.interval_seconds,
            "next_run_at": self.next_run_at,
            "enabled": self.enabled,
            "run_count": self.run_count,
            "last_task_id": self.last_task_id,
            "created_at": self.created_at,
        }


class TaskScheduler:
    """Submits tasks to a TaskQueue on a recurring interval."""

    def __init__(self) -> None:
        self._schedules: Dict[str, ScheduledTask] = {}
        self._queue: Optional[Any] = None
        self._runner: Optional[asyncio.Task] = None

    def attach_queue(self, queue: Any) -> None:
        self._queue = queue

    def schedule(
        self,
        objective: str,
        interval_seconds: float,
        parameters: Optional[Dict[str, Any]] = None,
        run_immediately: bool = False,
    ) -> ScheduledTask:
        """Register a recurring task. Returns the ScheduledTask record."""
        schedule_id = str(uuid.uuid4())
        next_run = time.time() if run_immediately else time.time() + interval_seconds
        task = ScheduledTask(
            schedule_id=schedule_id,
            objective=objective,
            parameters=parameters or {},
            interval_seconds=interval_seconds,
            next_run_at=next_run,
        )
        self._schedules[schedule_id] = task
        logger.info(
            "Scheduled task '%s' every %.0fs (id=%s)",
            objective[:50], interval_seconds, schedule_id,
        )
        return task

    def unschedule(self, schedule_id: str) -> bool:
        if schedule_id not in self._schedules:
            return False
        self._schedules[schedule_id].enabled = False
        del self._schedules[schedule_id]
        return True

    def pause(self, schedule_id: str) -> bool:
        task = self._schedules.get(schedule_id)
        if task is None:
            return False
        task.enabled = False
        return True

    def resume(self, schedule_id: str) -> bool:
        task = self._schedules.get(schedule_id)
        if task is None:
            return False
        task.enabled = True
        return True

    def list_schedules(self) -> List[ScheduledTask]:
        return list(self._schedules.values())

    def get(self, schedule_id: str) -> Optional[ScheduledTask]:
        return self._schedules.get(schedule_id)

    async def start(self) -> None:
        self._runner = asyncio.create_task(self._run_loop())
        logger.info("TaskScheduler started")

    async def stop(self) -> None:
        if self._runner:
            self._runner.cancel()
            try:
                await self._runner
            except asyncio.CancelledError:
                pass
        logger.info("TaskScheduler stopped")

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                return
            now = time.time()
            for sched in list(self._schedules.values()):
                if not sched.enabled or now < sched.next_run_at:
                    continue
                if self._queue is None:
                    continue
                try:
                    record = await self._queue.submit(sched.objective, sched.parameters)
                    sched.last_task_id = record.task_id
                    sched.run_count += 1
                    sched.next_run_at = now + sched.interval_seconds
                    logger.info(
                        "Scheduler fired '%s' → task %s (run #%d)",
                        sched.objective[:40], record.task_id, sched.run_count,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Scheduler submit failed for '%s': %s", sched.schedule_id, exc)
