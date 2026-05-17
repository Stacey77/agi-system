"""Unit tests for rate-limit middleware, sessions, webhooks, and eval."""

from __future__ import annotations

import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base_agent import AgentConfig, AgentType, BaseAgent


class _SimpleAgent(BaseAgent):
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "summary": "done", "output": f"result: {task.get('task','')}"}


def _cfg(name: str, t: AgentType = AgentType.RESEARCH) -> AgentConfig:
    return AgentConfig(name=name, agent_type=t)


# ---------------------------------------------------------------------------
# Rate-limit bucket
# ---------------------------------------------------------------------------

class TestRateLimitBucket:
    def test_bucket_allows_within_limit(self):
        from src.api.middleware.rate_limit import _Bucket
        b = _Bucket(capacity=5)
        for _ in range(5):
            assert b.consume(5, 1.0) is True

    def test_bucket_rejects_when_exhausted(self):
        from src.api.middleware.rate_limit import _Bucket
        b = _Bucket(capacity=2)
        b.consume(2, 1.0)
        b.consume(2, 1.0)
        assert b.consume(2, 1.0) is False

    def test_bucket_refills_over_time(self):
        from src.api.middleware.rate_limit import _Bucket
        b = _Bucket(capacity=1)
        b.consume(1, 10.0)
        b.last_refill -= 1.0
        assert b.consume(1, 10.0) is True


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

class TestMetricsHelpers:
    def test_record_agent_task_no_crash_without_prometheus(self):
        from src.api.middleware import metrics as m
        orig = m._PROMETHEUS_AVAILABLE
        m._PROMETHEUS_AVAILABLE = False
        try:
            m.record_agent_task("research_agent", "completed", 1.2)
        finally:
            m._PROMETHEUS_AVAILABLE = orig

    def test_metrics_response_returns_text_when_prometheus_missing(self):
        from src.api.middleware import metrics as m
        orig = m._PROMETHEUS_AVAILABLE
        m._PROMETHEUS_AVAILABLE = False
        try:
            resp = m.metrics_response()
            assert resp.status_code == 200
        finally:
            m._PROMETHEUS_AVAILABLE = orig


# ---------------------------------------------------------------------------
# WebhookDispatcher
# ---------------------------------------------------------------------------

class TestWebhookDispatcher:
    def test_register_returns_id(self):
        from src.webhooks.dispatcher import WebhookDispatcher
        d = WebhookDispatcher()
        wid = d.register("http://example.com/hook", ["task.completed"])
        assert isinstance(wid, str) and len(wid) > 0

    def test_unregister_existing(self):
        from src.webhooks.dispatcher import WebhookDispatcher
        d = WebhookDispatcher()
        wid = d.register("http://example.com/hook", ["crew.completed"])
        assert d.unregister(wid) is True

    def test_unregister_missing_returns_false(self):
        from src.webhooks.dispatcher import WebhookDispatcher
        d = WebhookDispatcher()
        assert d.unregister("nonexistent-id") is False

    def test_list_webhooks(self):
        from src.webhooks.dispatcher import WebhookDispatcher
        d = WebhookDispatcher()
        d.register("http://a.com", ["task.completed"])
        d.register("http://b.com", ["crew.completed"])
        hooks = d.list_webhooks()
        assert len(hooks) == 2

    @pytest.mark.asyncio
    async def test_dispatch_fires_matching_webhooks(self):
        from src.webhooks.dispatcher import WebhookDispatcher
        d = WebhookDispatcher()
        wid = d.register("http://example.com/hook", ["task.completed"])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock()
            mock_client_cls.return_value = mock_client
            await d.dispatch("task.completed", {"task_id": "123"})
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_skips_non_matching_events(self):
        from src.webhooks.dispatcher import WebhookDispatcher
        d = WebhookDispatcher()
        d.register("http://example.com/hook", ["task.completed"])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock()
            mock_client_cls.return_value = mock_client
            await d.dispatch("crew.completed", {"crew_id": "456"})
            mock_client.post.assert_not_called()


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class TestSessionManager:
    def test_create_session(self):
        from src.sessions.session_manager import SessionManager
        sm = SessionManager()
        session = sm.create_session("research_agent")
        assert session.agent_name == "research_agent"
        assert session.session_id is not None

    def test_get_session(self):
        from src.sessions.session_manager import SessionManager
        sm = SessionManager()
        s = sm.create_session("writing_agent")
        assert sm.get_session(s.session_id) is s

    def test_get_missing_session_returns_none(self):
        from src.sessions.session_manager import SessionManager
        sm = SessionManager()
        assert sm.get_session("nonexistent") is None

    def test_list_sessions(self):
        from src.sessions.session_manager import SessionManager
        sm = SessionManager()
        sm.create_session("research_agent")
        sm.create_session("analysis_agent")
        assert len(sm.list_sessions()) == 2

    def test_delete_session(self):
        from src.sessions.session_manager import SessionManager
        sm = SessionManager()
        s = sm.create_session("coding_agent")
        assert sm.delete_session(s.session_id) is True
        assert sm.get_session(s.session_id) is None

    def test_add_message(self):
        from src.sessions.session_manager import SessionManager
        sm = SessionManager()
        s = sm.create_session("review_agent")
        sm.add_message(s.session_id, "user", "Hello")
        sm.add_message(s.session_id, "assistant", "Hi there")
        assert len(s.messages) == 2
        assert s.messages[0]["role"] == "user"
        assert s.messages[1]["content"] == "Hi there"


# ---------------------------------------------------------------------------
# Integration: sessions + eval endpoints
# ---------------------------------------------------------------------------

class TestIntegrationEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        with TestClient(create_app()) as c:
            yield c

    def test_sessions_create(self, client):
        r = client.post("/api/v1/sessions", json={"agent_name": "research_agent"})
        assert r.status_code in (200, 201)
        assert "session_id" in r.json()

    def test_sessions_list(self, client):
        r = client.get("/api/v1/sessions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_session_send_message(self, client):
        r = client.post("/api/v1/sessions", json={"agent_name": "research_agent"})
        sid = r.json()["session_id"]
        r2 = client.post(f"/api/v1/sessions/{sid}/message", json={"message": "Tell me about AI"})
        assert r2.status_code == 200
        data = r2.json()
        assert data["role"] == "assistant"

    def test_session_history(self, client):
        r = client.post("/api/v1/sessions", json={"agent_name": "writing_agent"})
        sid = r.json()["session_id"]
        client.post(f"/api/v1/sessions/{sid}/message", json={"message": "Write a poem"})
        r2 = client.get(f"/api/v1/sessions/{sid}/history")
        assert r2.status_code == 200
        assert isinstance(r2.json(), list)

    def test_eval_benchmarks(self, client):
        r = client.get("/api/v1/eval/benchmarks")
        assert r.status_code == 200
        data = r.json()
        assert "benchmarks" in data

    def test_eval_run(self, client):
        r = client.post("/api/v1/eval/run", json={"agent_name": "research_agent"})
        assert r.status_code == 200
        data = r.json()
        assert "eval_id" in data
        assert "score" in data

    def test_webhooks_register(self, client):
        r = client.post("/api/v1/webhooks", json={
            "url": "http://example.com/hook",
            "events": ["task.completed"],
        })
        assert r.status_code in (200, 201)
        assert "webhook_id" in r.json()

    def test_webhooks_list(self, client):
        r = client.get("/api/v1/webhooks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_metrics_endpoint(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
