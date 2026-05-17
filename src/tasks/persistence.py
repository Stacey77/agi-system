"""SQLite-backed persistence for TaskRecord — optional, falls back to no-op."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from typing import Dict, List, Optional

from src.tasks.queue import TaskRecord, TaskStatus

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id     TEXT PRIMARY KEY,
    objective   TEXT NOT NULL,
    status      TEXT NOT NULL,
    result      TEXT,
    error       TEXT,
    created_at  REAL NOT NULL,
    started_at  REAL,
    completed_at REAL,
    progress    INTEGER NOT NULL DEFAULT 0,
    parameters  TEXT
);
"""


class TaskPersistence:
    """Synchronous SQLite store (uses a dedicated thread lock for safety)."""

    def __init__(self, db_path: str = "tasks.db") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        try:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute(_CREATE_TABLE)
            self._conn.commit()
            logger.info("TaskPersistence initialised at %s", self._db_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("TaskPersistence init failed (%s) — running without persistence", exc)
            self._conn = None

    def save(self, record: TaskRecord) -> None:
        if self._conn is None:
            return
        params = getattr(record, "parameters", {})
        with self._lock:
            try:
                self._conn.execute(
                    """
                    INSERT INTO tasks
                        (task_id, objective, status, result, error,
                         created_at, started_at, completed_at, progress, parameters)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        status=excluded.status,
                        result=excluded.result,
                        error=excluded.error,
                        started_at=excluded.started_at,
                        completed_at=excluded.completed_at,
                        progress=excluded.progress
                    """,
                    (
                        record.task_id,
                        record.objective,
                        record.status,
                        json.dumps(record.result) if record.result is not None else None,
                        record.error,
                        record.created_at,
                        record.started_at,
                        record.completed_at,
                        record.progress,
                        json.dumps(params),
                    ),
                )
                self._conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("TaskPersistence.save failed: %s", exc)

    def load_all(self) -> Dict[str, TaskRecord]:
        if self._conn is None:
            return {}
        records: Dict[str, TaskRecord] = {}
        with self._lock:
            try:
                cur = self._conn.execute(
                    "SELECT task_id, objective, status, result, error, "
                    "created_at, started_at, completed_at, progress FROM tasks"
                )
                for row in cur.fetchall():
                    (task_id, objective, status, result_json, error,
                     created_at, started_at, completed_at, progress) = row
                    r = TaskRecord(
                        task_id=task_id,
                        objective=objective,
                        status=TaskStatus(status),
                        result=json.loads(result_json) if result_json else None,
                        error=error,
                        created_at=created_at,
                        started_at=started_at,
                        completed_at=completed_at,
                        progress=progress,
                    )
                    records[task_id] = r
            except Exception as exc:  # noqa: BLE001
                logger.warning("TaskPersistence.load_all failed: %s", exc)
        return records

    def close(self) -> None:
        if self._conn:
            with self._lock:
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
            self._conn = None
