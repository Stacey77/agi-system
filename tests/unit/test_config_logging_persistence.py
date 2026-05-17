"""Tests for Settings, structured logging, and SQLite task persistence."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time

import pytest


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_defaults(self):
        from src.config import Settings
        s = Settings()
        assert s.llm_provider == "openai"
        assert s.rate_limit_requests == 100
        assert s.log_format == "json"

    def test_cors_origins_list_single(self):
        from src.config import Settings
        s = Settings(cors_origins="http://localhost:3000")
        assert s.cors_origins_list() == ["http://localhost:3000"]

    def test_cors_origins_list_multiple(self):
        from src.config import Settings
        s = Settings(cors_origins="http://a.com,http://b.com")
        assert len(s.cors_origins_list()) == 2

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("RATE_LIMIT_REQUESTS", "50")
        from importlib import reload
        import src.config as cfg_mod
        reload(cfg_mod)
        from src.config import Settings
        s = Settings()
        assert s.log_level == "DEBUG"
        assert s.rate_limit_requests == 50

    def test_jwt_secret_generated(self):
        from src.config import Settings
        s1 = Settings()
        s2 = Settings()
        # Both are valid hex strings (even if different due to default_factory)
        assert len(s1.jwt_secret) == 64


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

class TestJsonFormatter:
    def test_json_log_output(self):
        from src.logging_config import _JsonFormatter
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["msg"] == "hello world"
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert "ts" in data

    def test_json_log_with_exception(self):
        from src.logging_config import _JsonFormatter
        formatter = _JsonFormatter()
        try:
            raise ValueError("oops")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exc" in data
        assert "ValueError" in data["exc"]

    def test_configure_logging_text(self):
        from src.logging_config import configure_logging
        configure_logging(level="WARNING", fmt="text")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_configure_logging_json(self):
        from src.logging_config import configure_logging, _JsonFormatter
        configure_logging(level="INFO", fmt="json")
        root = logging.getLogger()
        assert any(isinstance(h.formatter, _JsonFormatter) for h in root.handlers)


# ---------------------------------------------------------------------------
# TaskPersistence
# ---------------------------------------------------------------------------

class TestTaskPersistence:
    def _make_persistence(self):
        from src.tasks.persistence import TaskPersistence
        tmp = tempfile.mktemp(suffix=".db")
        return TaskPersistence(db_path=tmp), tmp

    def test_save_and_load(self):
        from src.tasks.queue import TaskRecord, TaskStatus
        from src.tasks.persistence import TaskPersistence
        import tempfile

        tmp = tempfile.mktemp(suffix=".db")
        p = TaskPersistence(db_path=tmp)
        r = TaskRecord(task_id="t1", objective="do stuff")
        p.save(r)

        p2 = TaskPersistence(db_path=tmp)
        records = p2.load_all()
        assert "t1" in records
        assert records["t1"].objective == "do stuff"
        assert records["t1"].status == TaskStatus.QUEUED
        p.close()
        p2.close()

    def test_upsert_updates_status(self):
        from src.tasks.queue import TaskRecord, TaskStatus
        from src.tasks.persistence import TaskPersistence
        import tempfile

        tmp = tempfile.mktemp(suffix=".db")
        p = TaskPersistence(db_path=tmp)
        r = TaskRecord(task_id="t2", objective="update me")
        p.save(r)

        r.status = TaskStatus.COMPLETED
        r.result = {"summary": "done"}
        r.completed_at = time.time()
        r.progress = 100
        p.save(r)

        p2 = TaskPersistence(db_path=tmp)
        records = p2.load_all()
        assert records["t2"].status == TaskStatus.COMPLETED
        assert records["t2"].result == {"summary": "done"}
        p.close()
        p2.close()

    def test_load_empty_db(self):
        from src.tasks.persistence import TaskPersistence
        import tempfile

        tmp = tempfile.mktemp(suffix=".db")
        p = TaskPersistence(db_path=tmp)
        assert p.load_all() == {}
        p.close()

    def test_multiple_records(self):
        from src.tasks.queue import TaskRecord
        from src.tasks.persistence import TaskPersistence
        import tempfile

        tmp = tempfile.mktemp(suffix=".db")
        p = TaskPersistence(db_path=tmp)
        for i in range(5):
            p.save(TaskRecord(task_id=f"task-{i}", objective=f"obj-{i}"))
        p2 = TaskPersistence(db_path=tmp)
        records = p2.load_all()
        assert len(records) == 5
        p.close()
        p2.close()

    def test_close_is_idempotent(self):
        from src.tasks.persistence import TaskPersistence
        import tempfile

        tmp = tempfile.mktemp(suffix=".db")
        p = TaskPersistence(db_path=tmp)
        p.close()
        p.close()  # should not raise

    @pytest.mark.asyncio
    async def test_queue_persists_through_restart(self):
        from src.tasks.queue import TaskQueue, TaskStatus
        from src.tasks.persistence import TaskPersistence
        import tempfile

        tmp = tempfile.mktemp(suffix=".db")
        p1 = TaskPersistence(db_path=tmp)
        q1 = TaskQueue(persistence=p1)
        done = __import__("asyncio").Event()

        async def handler(record):
            done.set()

        await q1.start(handler)
        record = await q1.submit("persist me", {})
        task_id = record.task_id
        await __import__("asyncio").wait_for(done.wait(), timeout=5.0)
        await __import__("asyncio").sleep(0.1)
        await q1.stop()
        p1.close()

        # Restart with new queue + persistence pointing at same DB
        p2 = TaskPersistence(db_path=tmp)
        q2 = TaskQueue(persistence=p2)
        restored = q2.get(task_id)
        assert restored is not None
        assert restored.status == TaskStatus.COMPLETED
        p2.close()
