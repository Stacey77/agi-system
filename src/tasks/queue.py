"""Async task queue — Redis-backed with asyncio fallback."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    task_id: str
    objective: str
    status: TaskStatus = TaskStatus.QUEUED
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
        }


class TaskQueue:
    """Async task queue.

    Uses Redis when REDIS_URL is configured; otherwise falls back to an
    in-process asyncio.Queue so the system works without any external deps.
    Optionally persists records to SQLite via TaskPersistence.
    """

    def __init__(self, persistence: Optional[Any] = None) -> None:
        self._records: Dict[str, TaskRecord] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._handlers: Dict[str, Callable[..., Coroutine]] = {}
        self._redis: Optional[Any] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._persistence = persistence
        if persistence is not None:
            self._records = persistence.load_all()
            logger.info("TaskQueue restored %d records from persistence", len(self._records))

    async def start(self, handler: Callable[[TaskRecord], Coroutine]) -> None:
        """Start background worker with *handler* called for each task."""
        self._default_handler = handler
        redis_url = os.getenv("REDIS_URL", "")
        if redis_url:
            await self._init_redis(redis_url)
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("TaskQueue started (backend=%s)", "redis" if self._redis else "asyncio")

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:  # noqa: BLE001
                pass

    async def submit(self, objective: str, parameters: Dict[str, Any] = {}) -> TaskRecord:
        task_id = str(uuid.uuid4())
        record = TaskRecord(task_id=task_id, objective=objective)
        record.__dict__.update({"parameters": parameters})
        self._records[task_id] = record
        if self._persistence:
            self._persistence.save(record)
        await self._enqueue(task_id)
        await self._notify(task_id, "queued")
        logger.info("Task '%s' submitted: %s", task_id, objective[:60])
        return record

    def get(self, task_id: str) -> Optional[TaskRecord]:
        return self._records.get(task_id)

    def list_all(self) -> List[TaskRecord]:
        return list(self._records.values())

    def cancel(self, task_id: str) -> bool:
        record = self._records.get(task_id)
        if record is None or record.status not in (TaskStatus.QUEUED, TaskStatus.RUNNING):
            return False
        record.status = TaskStatus.CANCELLED
        return True

    async def subscribe(self, task_id: str) -> asyncio.Queue:
        """Return a queue that receives status updates for *task_id*."""
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subscribers.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(task_id, [])
        if q in subs:
            subs.remove(q)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _init_redis(self, url: str) -> None:
        try:
            import redis.asyncio as aioredis  # type: ignore[import]
            self._redis = aioredis.from_url(url, decode_responses=True)
            await self._redis.ping()
            logger.info("TaskQueue connected to Redis at %s", url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable (%s) — using asyncio fallback", exc)
            self._redis = None

    async def _enqueue(self, task_id: str) -> None:
        if self._redis:
            try:
                await self._redis.rpush("agi:task_queue", task_id)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis enqueue failed: %s — using asyncio", exc)
        await self._queue.put(task_id)

    async def _dequeue(self) -> str:
        if self._redis:
            try:
                result = await self._redis.blpop("agi:task_queue", timeout=1)
                if result:
                    return result[1]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis dequeue failed: %s — draining asyncio queue", exc)
        return await self._queue.get()

    async def _worker(self) -> None:
        logger.info("TaskQueue worker started")
        while True:
            try:
                task_id = await asyncio.wait_for(self._dequeue(), timeout=2.0)
            except asyncio.CancelledError:
                logger.info("TaskQueue worker cancelled")
                raise
            except asyncio.TimeoutError:
                await asyncio.sleep(0)
                continue
            except Exception as exc:  # noqa: BLE001
                logger.error("TaskQueue dequeue error: %s", exc)
                await asyncio.sleep(1)
                continue

            record = self._records.get(task_id)
            if record is None or record.status == TaskStatus.CANCELLED:
                continue

            record.status = TaskStatus.RUNNING
            record.started_at = time.time()
            await self._notify(task_id, "running")

            try:
                await self._default_handler(record)
                if record.status != TaskStatus.CANCELLED:
                    record.status = TaskStatus.COMPLETED
                    record.completed_at = time.time()
                    record.progress = 100
                    await self._notify(task_id, "completed")
            except Exception as exc:  # noqa: BLE001
                logger.error("Task '%s' handler failed: %s", task_id, exc)
                record.status = TaskStatus.FAILED
                record.error = str(exc)
                record.completed_at = time.time()
                await self._notify(task_id, "failed")

    async def _notify(self, task_id: str, event: str) -> None:
        record = self._records.get(task_id)
        if record is None:
            return
        if self._persistence:
            self._persistence.save(record)
        payload = {"event": event, **record.to_dict()}
        for q in list(self._subscribers.get(task_id, [])):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass
