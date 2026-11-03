"""Unit tests for the workforce package and API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.auth.key_store import KeyRole


def _api_key_mock(role: str = "admin"):
    m = MagicMock()
    m.role = KeyRole(role)
    m.key_id = "k1"
    m.name = "test"
    return m


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from src.api.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        app.state.key_store = MagicMock()
        app.state.key_store.validate_key.return_value = _api_key_mock()
        app.state.jwt_manager = MagicMock()
        app.state.jwt_manager.verify_token.return_value = None
        yield c


H = {"X-API-Key": "sk-test"}


# ---------------------------------------------------------------------------
# WorkerPool unit tests
# ---------------------------------------------------------------------------


class TestWorkerPool:
    @pytest.fixture()
    def pool(self):
        from src.workforce.worker_pool import WorkerPool

        return WorkerPool()

    def test_add_worker(self, pool):
        w = pool.add_worker("Alice", "coding", ["python", "java"])
        assert w.name == "Alice"
        assert w.status == "idle"

    def test_get_worker(self, pool):
        w = pool.add_worker("Bob", "research", [])
        fetched = pool.get_worker(w.worker_id)
        assert fetched is w

    def test_remove_worker(self, pool):
        w = pool.add_worker("Charlie", "planning", [])
        assert pool.remove_worker(w.worker_id) is True
        assert pool.get_worker(w.worker_id) is None

    def test_remove_missing_worker_returns_false(self, pool):
        assert pool.remove_worker("nonexistent") is False

    def test_list_workers_by_status(self, pool):
        pool.add_worker("Idle1", "coding", [])
        pool.add_worker("Idle2", "coding", [])
        idle = pool.list_workers(status="idle")
        assert len(idle) >= 2

    def test_list_workers_by_skill(self, pool):
        pool.add_worker("SpecialistA", "analysis", ["ml", "nlp"])
        pool.add_worker("GeneralistB", "coding", ["python"])
        ml_workers = pool.list_workers(skill="ml")
        assert any(w.name == "SpecialistA" for w in ml_workers)
        assert not any(w.name == "GeneralistB" for w in ml_workers)

    def test_assign_task(self, pool):
        w = pool.add_worker("Worker1", "coding", [])
        assert pool.assign_task(w.worker_id, "task-123") is True
        assert w.status == "busy"
        assert w.current_task_id == "task-123"

    def test_assign_task_to_busy_worker_fails(self, pool):
        w = pool.add_worker("Worker2", "coding", [])
        pool.assign_task(w.worker_id, "task-a")
        assert pool.assign_task(w.worker_id, "task-b") is False

    def test_complete_task_success(self, pool):
        w = pool.add_worker("Worker3", "coding", [])
        pool.assign_task(w.worker_id, "task-x")
        pool.complete_task(w.worker_id, success=True)
        assert w.status == "idle"
        assert w.tasks_completed == 1
        assert w.current_task_id is None

    def test_complete_task_failure(self, pool):
        w = pool.add_worker("Worker4", "coding", [])
        pool.assign_task(w.worker_id, "task-y")
        pool.complete_task(w.worker_id, success=False)
        assert w.tasks_failed == 1

    def test_find_available_any(self, pool):
        pool.add_worker("FreeW", "coding", [])
        w = pool.find_available()
        assert w is not None

    def test_find_available_by_skill(self, pool):
        pool.add_worker("SkillWorker", "analysis", ["special_skill"])
        w = pool.find_available(required_skills=["special_skill"])
        assert w is not None
        assert "special_skill" in w.skills

    def test_find_available_none_when_all_busy(self, pool):
        fresh_pool = __import__(
            "src.workforce.worker_pool", fromlist=["WorkerPool"]
        ).WorkerPool()
        w = fresh_pool.add_worker("OnlyWorker", "coding", [])
        fresh_pool.assign_task(w.worker_id, "t1")
        assert fresh_pool.find_available() is None

    def test_stats(self, pool):
        s = pool.stats()
        assert "total" in s
        assert "idle" in s
        assert "busy" in s
        assert "tasks_completed" in s

    def test_to_dict_keys(self, pool):
        w = pool.add_worker("DictWorker", "writing", ["english"])
        d = w.to_dict()
        assert d["name"] == "DictWorker"
        assert "worker_id" in d
        assert "status" in d


# ---------------------------------------------------------------------------
# TaskDispatcher unit tests
# ---------------------------------------------------------------------------


class TestTaskDispatcher:
    @pytest.fixture()
    def dispatcher(self):
        from src.workforce.task_dispatcher import TaskDispatcher
        from src.workforce.worker_pool import WorkerPool

        pool = WorkerPool()
        pool.add_worker("DispatchWorker", "planning", ["planning"])
        return TaskDispatcher(pool)

    @pytest.mark.asyncio
    async def test_dispatch_assigns_worker(self, dispatcher):
        result = await dispatcher.dispatch("do something", required_skills=["planning"])
        assert result["status"] in ("assigned", "queued")
        if result["status"] == "assigned":
            assert result["worker_id"] is not None

    @pytest.mark.asyncio
    async def test_dispatch_no_available_worker(self):
        from src.workforce.task_dispatcher import TaskDispatcher
        from src.workforce.worker_pool import WorkerPool

        pool = WorkerPool()
        d = TaskDispatcher(pool)
        result = await d.dispatch("do something")
        assert result["status"] == "queued"

    @pytest.mark.asyncio
    async def test_get_assignment(self, dispatcher):
        result = await dispatcher.dispatch("task-abc", required_skills=["planning"])
        tid = result["task_id"]
        assignment = dispatcher.get_assignment(tid)
        assert assignment is not None

    @pytest.mark.asyncio
    async def test_dispatch_batch(self):
        from src.workforce.task_dispatcher import TaskDispatcher
        from src.workforce.worker_pool import WorkerPool

        pool = WorkerPool()
        for i in range(3):
            pool.add_worker(f"BW{i}", "coding", [])
        d = TaskDispatcher(pool)
        objectives = ["task1", "task2", "task3"]
        results = await d.dispatch_batch(objectives)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Workforce API endpoint tests
# ---------------------------------------------------------------------------


class TestWorkforceAPI:
    def test_list_workers(self, client):
        resp = client.get("/api/v1/workforce/workers", headers=H)
        assert resp.status_code == 200
        assert "workers" in resp.json()

    def test_hire_worker(self, client):
        resp = client.post(
            "/api/v1/workforce/hire",
            headers=H,
            json={"name": "TestWorker", "agent_type": "coding", "skills": ["python"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "worker_id" in data

    def test_fire_worker(self, client):
        hire = client.post(
            "/api/v1/workforce/hire",
            headers=H,
            json={"name": "FireWorker", "agent_type": "coding", "skills": []},
        )
        wid = hire.json()["worker_id"]
        resp = client.delete(f"/api/v1/workforce/workers/{wid}", headers=H)
        assert resp.status_code == 200

    def test_fire_missing_worker_404(self, client):
        resp = client.delete("/api/v1/workforce/workers/nonexistent", headers=H)
        assert resp.status_code == 404

    def test_workforce_status(self, client):
        resp = client.get("/api/v1/workforce/status", headers=H)
        assert resp.status_code == 200

    def test_assign_objective(self, client):
        # Hire a worker first
        client.post(
            "/api/v1/workforce/hire",
            headers=H,
            json={"name": "DispWorker", "agent_type": "planning", "skills": []},
        )
        resp = client.post(
            "/api/v1/workforce/assign",
            headers=H,
            json={"objective": "Do something important"},
        )
        assert resp.status_code == 200
