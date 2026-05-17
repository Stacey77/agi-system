"""Tests for task scheduler, token tracker, usage endpoints, and task list pagination."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.llm.token_tracker import TokenTracker, UsageRecord


# ---------------------------------------------------------------------------
# TokenTracker unit tests
# ---------------------------------------------------------------------------

class TestTokenTracker:
    def test_record_returns_usage_record(self):
        tracker = TokenTracker()
        r = tracker.record(agent_name="agent_a", model="gpt-4o-mini", input_tokens=100, output_tokens=50)
        assert isinstance(r, UsageRecord)
        assert r.total_tokens == 150
        assert r.agent_name == "agent_a"

    def test_estimated_cost_known_model(self):
        tracker = TokenTracker()
        r = tracker.record(agent_name="x", model="gpt-4o-mini", input_tokens=1000, output_tokens=1000)
        # gpt-4o-mini: input=0.00015/1k, output=0.0006/1k → 0.00015 + 0.0006 = 0.00075
        assert abs(r.estimated_cost_usd - 0.00075) < 1e-9

    def test_estimated_cost_unknown_model_uses_default(self):
        tracker = TokenTracker()
        r = tracker.record(agent_name="x", model="unknown-model", input_tokens=1000, output_tokens=1000)
        # default: 0.002/1k each → 0.004
        assert abs(r.estimated_cost_usd - 0.004) < 1e-9

    def test_summary_aggregates_by_agent(self):
        tracker = TokenTracker()
        tracker.record("agent_a", "gpt-4o-mini", 100, 50)
        tracker.record("agent_a", "gpt-4o-mini", 200, 100)
        tracker.record("agent_b", "gpt-4o-mini", 50, 25)
        summary = tracker.summary()
        assert summary["total_tokens"] == 525
        assert summary["total_calls"] == 3
        assert "agent_a" in summary["by_agent"]
        assert summary["by_agent"]["agent_a"]["total_tokens"] == 450
        assert summary["by_agent"]["agent_a"]["calls"] == 2
        assert summary["by_agent"]["agent_b"]["total_tokens"] == 75

    def test_summary_empty(self):
        tracker = TokenTracker()
        s = tracker.summary()
        assert s["total_tokens"] == 0
        assert s["total_calls"] == 0
        assert s["by_agent"] == {}

    def test_records_for_task(self):
        tracker = TokenTracker()
        tracker.record("a", "gpt-4o-mini", 10, 5, task_id="task-1")
        tracker.record("b", "gpt-4o-mini", 20, 10, task_id="task-2")
        tracker.record("c", "gpt-4o-mini", 30, 15, task_id="task-1")
        records = tracker.records_for_task("task-1")
        assert len(records) == 2
        assert all(r["task_id"] == "task-1" for r in records)

    def test_records_for_task_empty(self):
        tracker = TokenTracker()
        assert tracker.records_for_task("nonexistent") == []

    def test_max_records_eviction(self):
        tracker = TokenTracker(max_records=5)
        for i in range(10):
            tracker.record("a", "gpt-4o-mini", i, i)
        assert len(tracker._records) == 5

    def test_to_dict_contains_required_fields(self):
        tracker = TokenTracker()
        r = tracker.record("agent", "gpt-4o-mini", 100, 50, task_id="t1")
        d = r.to_dict()
        for key in ("agent_name", "task_id", "model", "input_tokens", "output_tokens",
                    "total_tokens", "estimated_cost_usd", "timestamp"):
            assert key in d

    def test_thread_safe_concurrent_records(self):
        import threading
        tracker = TokenTracker()
        errors = []

        def worker():
            try:
                for _ in range(50):
                    tracker.record("agent", "gpt-4o-mini", 10, 5)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert tracker.summary()["total_calls"] == 200


# ---------------------------------------------------------------------------
# TaskScheduler unit tests
# ---------------------------------------------------------------------------

class TestTaskScheduler:
    def test_schedule_returns_scheduled_task(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        sched = scheduler.schedule(objective="test", interval_seconds=60)
        assert sched.schedule_id
        assert sched.objective == "test"
        assert sched.interval_seconds == 60
        assert sched.enabled is True

    def test_list_schedules(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        scheduler.schedule(objective="job1", interval_seconds=30)
        scheduler.schedule(objective="job2", interval_seconds=60)
        schedules = scheduler.list_schedules()
        assert len(schedules) == 2

    def test_get_existing(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        sched = scheduler.schedule("task", 10)
        assert scheduler.get(sched.schedule_id) is sched

    def test_get_missing_returns_none(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        assert scheduler.get("nonexistent") is None

    def test_unschedule(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        sched = scheduler.schedule("task", 10)
        assert scheduler.unschedule(sched.schedule_id) is True
        assert scheduler.get(sched.schedule_id) is None

    def test_unschedule_missing_returns_false(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        assert scheduler.unschedule("nonexistent") is False

    def test_pause_and_resume(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        sched = scheduler.schedule("task", 10)
        assert scheduler.pause(sched.schedule_id) is True
        assert scheduler.get(sched.schedule_id).enabled is False
        assert scheduler.resume(sched.schedule_id) is True
        assert scheduler.get(sched.schedule_id).enabled is True

    def test_pause_missing_returns_false(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        assert scheduler.pause("nonexistent") is False

    def test_run_immediately_sets_next_run_in_past(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        sched = scheduler.schedule("task", 60, run_immediately=True)
        # next_run_at should be at or before the current time (within a small margin)
        assert sched.next_run_at <= time.time() + 0.01

    def test_to_dict_keys(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        sched = scheduler.schedule("task", 10)
        d = sched.to_dict()
        for key in ("schedule_id", "objective", "interval_seconds", "next_run_at",
                    "enabled", "run_count", "created_at"):
            assert key in d

    @pytest.mark.asyncio
    async def test_start_stop(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        await scheduler.start()
        assert scheduler._runner is not None
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_submits_due_tasks(self):
        from src.tasks.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        submitted = []

        class FakeQueue:
            async def submit(self, objective, parameters=None):
                submitted.append(objective)
                return MagicMock(task_id="t1")

        scheduler.attach_queue(FakeQueue())
        scheduler.schedule("urgent", interval_seconds=100, run_immediately=True)
        await scheduler.start()
        await asyncio.sleep(1.5)  # loop sleeps 1s before first check
        await scheduler.stop()
        assert "urgent" in submitted


# ---------------------------------------------------------------------------
# Usage endpoint tests
# ---------------------------------------------------------------------------

def _make_api_key_mock(role_str: str = "admin"):
    from src.auth.key_store import ApiKey, KeyRole
    mock_key = MagicMock(spec=ApiKey)
    mock_key.role = KeyRole(role_str)
    mock_key.key_id = "k1"
    mock_key.name = "test"
    return mock_key


@pytest.fixture()
def client_with_tracker():
    from src.api.main import create_app
    app = create_app()
    tracker = TokenTracker()
    tracker.record("agent_x", "gpt-4o-mini", 500, 250, task_id="task-abc")
    tracker.record("agent_y", "gpt-4o-mini", 100, 50)

    with TestClient(app, raise_server_exceptions=True) as c:
        app.state.token_tracker = tracker
        app.state.key_store = MagicMock()
        app.state.key_store.validate_key.return_value = _make_api_key_mock()
        app.state.jwt_manager = MagicMock()
        app.state.jwt_manager.verify_token.return_value = None
        yield c


class TestUsageEndpoints:
    def test_summary_returns_aggregate(self, client_with_tracker):
        resp = client_with_tracker.get(
            "/api/v1/usage/", headers={"X-API-Key": "sk-test"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tokens" in data
        assert "by_agent" in data

    def test_task_usage(self, client_with_tracker):
        resp = client_with_tracker.get(
            "/api/v1/usage/tasks/task-abc", headers={"X-API-Key": "sk-test"}
        )
        assert resp.status_code == 200
        records = resp.json()
        assert isinstance(records, list)
        assert all(r["task_id"] == "task-abc" for r in records)

    def test_task_usage_empty(self, client_with_tracker):
        resp = client_with_tracker.get(
            "/api/v1/usage/tasks/nonexistent", headers={"X-API-Key": "sk-test"}
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Task list pagination tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_with_tasks():
    from src.api.main import create_app
    from src.tasks.queue import TaskStatus
    app = create_app()

    queue = MagicMock()
    task_list = []
    for i in range(15):
        tid = f"task-{i:03d}"
        r = MagicMock()
        r.task_id = tid
        r.status = "completed" if i % 2 == 0 else "failed"
        r.objective = f"obj-{i}"
        r.created_at = time.time() - (15 - i)
        r.updated_at = r.created_at
        r.result = None
        r.progress = 100
        r.progress_message = ""
        r.to_dict.return_value = {
            "task_id": tid, "status": r.status, "objective": r.objective,
            "created_at": r.created_at,
        }
        task_list.append(r)

    queue.list_all.return_value = task_list

    with TestClient(app, raise_server_exceptions=True) as c:
        app.state.task_queue = queue
        app.state.key_store = MagicMock()
        app.state.key_store.validate_key.return_value = _make_api_key_mock()
        app.state.jwt_manager = MagicMock()
        app.state.jwt_manager.verify_token.return_value = None
        yield c


class TestTaskPagination:
    def test_list_tasks_default(self, client_with_tasks):
        resp = client_with_tasks.get("/api/v1/tasks/", headers={"X-API-Key": "sk-test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "total" in data

    def test_list_tasks_limit(self, client_with_tasks):
        resp = client_with_tasks.get(
            "/api/v1/tasks/?limit=5", headers={"X-API-Key": "sk-test"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) <= 5

    def test_list_tasks_status_filter(self, client_with_tasks):
        resp = client_with_tasks.get(
            "/api/v1/tasks/?status=completed", headers={"X-API-Key": "sk-test"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for task in data["tasks"]:
            assert task["status"] == "completed"

    def test_list_tasks_offset(self, client_with_tasks):
        resp_full = client_with_tasks.get(
            "/api/v1/tasks/?limit=10&offset=0", headers={"X-API-Key": "sk-test"}
        )
        resp_offset = client_with_tasks.get(
            "/api/v1/tasks/?limit=10&offset=5", headers={"X-API-Key": "sk-test"}
        )
        assert resp_full.status_code == 200
        assert resp_offset.status_code == 200
        full_ids = [t["task_id"] for t in resp_full.json()["tasks"]]
        offset_ids = [t["task_id"] for t in resp_offset.json()["tasks"]]
        # Offset result should be different from start
        assert full_ids != offset_ids

    def test_list_tasks_limit_clamped(self, client_with_tasks):
        resp = client_with_tasks.get(
            "/api/v1/tasks/?limit=9999", headers={"X-API-Key": "sk-test"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) <= 500
