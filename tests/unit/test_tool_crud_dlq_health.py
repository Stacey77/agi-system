"""Tests for tool CRUD, dead-letter queue, body-limit middleware, and health memory metrics."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.auth.key_store import KeyRole


def _api_key_mock(role: str = "admin"):
    m = MagicMock()
    m.role = KeyRole(role)
    m.key_id = "k1"
    m.name = "test"
    return m


@pytest.fixture(scope="module")
def client():
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
# ToolLandscape unit tests
# ---------------------------------------------------------------------------

class TestToolLandscapeUnit:
    def test_remove_tool(self):
        from src.platform.tool_landscape import ToolLandscape
        ls = ToolLandscape(load_defaults=False)
        tool = ls.register_tool(name="mytool", description="test")
        tid = tool.tool_id
        assert ls.remove_tool(tid) is True
        assert ls.get_tool(tid) is None

    def test_remove_missing_returns_false(self):
        from src.platform.tool_landscape import ToolLandscape
        ls = ToolLandscape(load_defaults=False)
        assert ls.remove_tool("nonexistent") is False

    def test_update_tool(self):
        from src.platform.tool_landscape import ToolLandscape
        ls = ToolLandscape(load_defaults=False)
        tool = ls.register_tool(name="updatable", description="original")
        updated = ls.update_tool(tool.tool_id, description="updated", version="2.0")
        assert updated is not None
        assert updated.description == "updated"
        assert updated.version == "2.0"

    def test_update_missing_returns_none(self):
        from src.platform.tool_landscape import ToolLandscape
        ls = ToolLandscape(load_defaults=False)
        assert ls.update_tool("nonexistent", description="x") is None


# ---------------------------------------------------------------------------
# Platform tool CRUD endpoints
# ---------------------------------------------------------------------------

class TestPlatformToolCRUD:
    @pytest.fixture(autouse=True)
    def _register_test_tool(self, client):
        resp = client.post("/api/v1/platform/tools", headers=H, json={
            "name": "crud_tool",
            "description": "A test tool",
            "category": "ci_cd",
        })
        assert resp.status_code == 200
        self._tool_id = resp.json()["tool"]["tool_id"]

    def test_get_tool(self, client):
        resp = client.get(f"/api/v1/platform/tools/{self._tool_id}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["tool"]["tool_id"] == self._tool_id

    def test_get_missing_tool_404(self, client):
        resp = client.get("/api/v1/platform/tools/nonexistent", headers=H)
        assert resp.status_code == 404

    def test_patch_tool(self, client):
        resp = client.patch(f"/api/v1/platform/tools/{self._tool_id}", headers=H,
                            json={"description": "patched", "version": "3.0"})
        assert resp.status_code == 200
        data = resp.json()["tool"]
        assert data["description"] == "patched"
        assert data["version"] == "3.0"

    def test_patch_missing_tool_404(self, client):
        resp = client.patch("/api/v1/platform/tools/nonexistent", headers=H,
                            json={"description": "x"})
        assert resp.status_code == 404

    def test_delete_tool(self, client):
        # Register a disposable tool
        r = client.post("/api/v1/platform/tools", headers=H,
                        json={"name": "disposable_tool", "description": "bye"})
        tid = r.json()["tool"]["tool_id"]
        resp = client.delete(f"/api/v1/platform/tools/{tid}", headers=H)
        assert resp.status_code == 200
        resp2 = client.get(f"/api/v1/platform/tools/{tid}", headers=H)
        assert resp2.status_code == 404

    def test_delete_missing_tool_404(self, client):
        resp = client.delete("/api/v1/platform/tools/nonexistent", headers=H)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Dead-letter queue endpoint
# ---------------------------------------------------------------------------

class TestDeadLetterQueue:
    @pytest.fixture()
    def dlq_client(self):
        from src.api.main import create_app
        from src.tasks.queue import TaskRecord, TaskStatus
        app = create_app()

        queue = MagicMock()
        records = []
        for i in range(5):
            r = MagicMock(spec=TaskRecord)
            r.task_id = f"fail-{i}"
            r.status = TaskStatus.FAILED
            r.objective = f"obj-{i}"
            r.created_at = time.time() - (10 - i)
            r.completed_at = r.created_at + 1.0
            r.result = {"error": "simulated failure"}
            r.error = "simulated failure"
            r.to_dict.return_value = {
                "task_id": r.task_id, "status": "failed", "error": r.error,
                "objective": r.objective, "created_at": r.created_at,
            }
            records.append(r)
        # Add one non-failed task
        ok = MagicMock(spec=TaskRecord)
        ok.task_id = "ok-1"
        ok.status = TaskStatus.COMPLETED
        ok.completed_at = time.time()
        records.append(ok)

        queue.list_all.return_value = records

        with TestClient(app, raise_server_exceptions=True) as c:
            app.state.task_queue = queue
            app.state.key_store = MagicMock()
            app.state.key_store.validate_key.return_value = _api_key_mock()
            app.state.jwt_manager = MagicMock()
            app.state.jwt_manager.verify_token.return_value = None
            yield c

    def test_dlq_returns_only_failed(self, dlq_client):
        resp = dlq_client.get("/api/v1/tasks/dead-letter", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for t in data["tasks"]:
            assert t["status"] == "failed"

    def test_dlq_pagination(self, dlq_client):
        resp = dlq_client.get("/api/v1/tasks/dead-letter?limit=2&offset=0", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 2
        assert data["total"] == 5

    def test_dlq_limit_clamped(self, dlq_client):
        resp = dlq_client.get("/api/v1/tasks/dead-letter?limit=9999", headers=H)
        assert resp.status_code == 200
        assert len(resp.json()["tasks"]) <= 500


# ---------------------------------------------------------------------------
# Body limit middleware
# ---------------------------------------------------------------------------

class TestBodyLimitMiddleware:
    def test_small_body_passes(self, client):
        resp = client.post("/api/v1/tasks/", headers=H,
                           json={"objective": "small"})
        assert resp.status_code != 413

    def test_oversized_content_length_rejected(self):
        from src.api.main import create_app
        from src.api.middleware.body_limit import BodyLimitMiddleware
        app = create_app()
        # Override to 10 bytes max so we can trigger it easily
        # We test the middleware directly
        from src.api.middleware.body_limit import BodyLimitMiddleware
        from starlette.testclient import TestClient as StarletteClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        async def dummy(req):
            return PlainTextResponse("ok")

        mini_app = Starlette(routes=[Route("/", dummy, methods=["POST"])])
        mini_app.add_middleware(BodyLimitMiddleware, max_bytes=10)
        with StarletteClient(mini_app) as tc:
            resp = tc.post("/", content=b"x" * 11,
                           headers={"content-length": "11"})
            assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Health detailed — process_memory component
# ---------------------------------------------------------------------------

class TestHealthMemoryMetric:
    def test_detailed_health_has_memory(self, client):
        resp = client.get("/health/detailed", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert "process_memory" in data["components"]
        mem = data["components"]["process_memory"]
        assert mem["status"] in ("healthy", "unavailable")

    def test_memory_rss_positive_when_healthy(self, client):
        resp = client.get("/health/detailed", headers=H)
        data = resp.json()
        mem = data["components"]["process_memory"]
        if mem["status"] == "healthy":
            assert mem["rss_bytes"] > 0
            assert mem["rss_mb"] > 0
