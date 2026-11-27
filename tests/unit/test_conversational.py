"""Unit tests for conversational package and API endpoints."""

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
# ConversationManager unit tests
# ---------------------------------------------------------------------------


class TestConversationManager:
    @pytest.fixture()
    def manager(self, tmp_path):
        from src.conversational.conversation_manager import ConversationManager

        return ConversationManager(db_path=str(tmp_path / "conv_test.db"))

    @pytest.mark.asyncio
    async def test_create_session(self, manager):
        session = await manager.create_session("agent1")
        assert "session_id" in session
        assert session["agent_name"] == "agent1"
        assert session["message_count"] == 0

    @pytest.mark.asyncio
    async def test_create_session_with_metadata(self, manager):
        session = await manager.create_session("agent2", metadata={"key": "val"})
        assert session["metadata"] == {"key": "val"}

    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        created = await manager.create_session("agent1")
        sid = created["session_id"]
        fetched = await manager.get_session(sid)
        assert fetched is not None
        assert fetched["session_id"] == sid

    @pytest.mark.asyncio
    async def test_get_missing_session_returns_none(self, manager):
        result = await manager.get_session("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, manager):
        await manager.create_session("agentX")
        await manager.create_session("agentX")
        sessions = await manager.list_sessions(agent_name="agentX")
        assert len(sessions) >= 2

    @pytest.mark.asyncio
    async def test_delete_session(self, manager):
        session = await manager.create_session("agent1")
        sid = session["session_id"]
        deleted = await manager.delete_session(sid)
        assert deleted is True
        assert await manager.get_session(sid) is None

    @pytest.mark.asyncio
    async def test_delete_missing_session_returns_false(self, manager):
        result = await manager.delete_session("no-such-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_add_and_get_messages(self, manager):
        session = await manager.create_session("agent1")
        sid = session["session_id"]
        await manager.add_message(sid, "user", "hello")
        await manager.add_message(sid, "assistant", "hi there")
        msgs = await manager.get_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_message_count_in_session(self, manager):
        session = await manager.create_session("agent1")
        sid = session["session_id"]
        await manager.add_message(sid, "user", "a")
        await manager.add_message(sid, "assistant", "b")
        fetched = await manager.get_session(sid)
        assert fetched["message_count"] == 2

    @pytest.mark.asyncio
    async def test_get_context_window_truncates(self, manager):
        session = await manager.create_session("agent1")
        sid = session["session_id"]
        for i in range(10):
            await manager.add_message(sid, "user", "x" * 400)
        # max_tokens=500 should exclude most messages
        window = await manager.get_context_window(sid, max_tokens=500)
        assert len(window) < 10

    @pytest.mark.asyncio
    async def test_clear_messages(self, manager):
        session = await manager.create_session("agent1")
        sid = session["session_id"]
        await manager.add_message(sid, "user", "hello")
        n = await manager.clear_messages(sid)
        assert n == 1
        msgs = await manager.get_messages(sid)
        assert msgs == []


# ---------------------------------------------------------------------------
# IntentClassifier unit tests
# ---------------------------------------------------------------------------


class TestIntentClassifier:
    @pytest.fixture()
    def clf(self):
        from src.conversational.intent_classifier import IntentClassifier

        return IntentClassifier()

    @pytest.mark.asyncio
    async def test_greeting_intent(self, clf):
        result = await clf.classify("Hello!")
        assert result["intent"] == "greeting"
        assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_farewell_intent(self, clf):
        result = await clf.classify("Goodbye for now")
        assert result["intent"] == "farewell"

    @pytest.mark.asyncio
    async def test_question_intent(self, clf):
        result = await clf.classify("What is the capital of France?")
        assert result["intent"] == "question"

    @pytest.mark.asyncio
    async def test_task_request_intent(self, clf):
        result = await clf.classify("Please create a report for Q3")
        assert result["intent"] == "task_request"

    @pytest.mark.asyncio
    async def test_complaint_intent(self, clf):
        result = await clf.classify("This is broken and not working")
        assert result["intent"] == "complaint"

    @pytest.mark.asyncio
    async def test_command_intent(self, clf):
        result = await clf.classify("Start the deployment process")
        assert result["intent"] == "command"

    @pytest.mark.asyncio
    async def test_suggested_agent_mapping(self, clf):
        result = await clf.classify("Please research this topic")
        # research triggers task_request -> planning_agent
        assert result["suggested_agent"] != ""

    @pytest.mark.asyncio
    async def test_returns_all_keys(self, clf):
        result = await clf.classify("What time is it?")
        assert "intent" in result
        assert "confidence" in result
        assert "entities" in result
        assert "suggested_agent" in result

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        from src.conversational.intent_classifier import IntentClassifier

        bad_llm = MagicMock()
        bad_llm.agenerate = MagicMock(side_effect=RuntimeError("LLM down"))
        clf = IntentClassifier(llm=bad_llm)
        result = await clf.classify("Hello there")
        assert result["intent"] in IntentClassifier.INTENTS


# ---------------------------------------------------------------------------
# ContextTracker unit tests
# ---------------------------------------------------------------------------


class TestContextTracker:
    @pytest.fixture()
    def tracker(self):
        from src.conversational.context_tracker import ContextTracker

        return ContextTracker(max_messages=5, max_tokens=200)

    def test_add_and_get_context(self, tracker):
        tracker.add_message("s1", "user", "hello")
        ctx = tracker.get_context("s1")
        assert len(ctx) == 1
        assert ctx[0]["role"] == "user"

    def test_sliding_window_limits_messages(self, tracker):
        for i in range(10):
            tracker.add_message("s2", "user", f"msg {i}")
        ctx = tracker.get_context("s2")
        assert len(ctx) <= 5

    def test_clear_session(self, tracker):
        tracker.add_message("s3", "user", "hi")
        tracker.clear("s3")
        assert tracker.get_context("s3") == []

    def test_session_count(self, tracker):
        tracker.add_message("sA", "user", "a")
        tracker.add_message("sB", "user", "b")
        assert tracker.session_count() == 2

    def test_empty_session_returns_empty_list(self, tracker):
        assert tracker.get_context("unknown-session") == []

    @pytest.mark.asyncio
    async def test_summarize_no_llm_truncates(self, tracker):
        for i in range(5):
            tracker.add_message("s4", "user", "x" * 50)
        await tracker.summarize_if_needed("s4", llm=None)
        ctx = tracker.get_context("s4")
        assert len(ctx) <= 5

    @pytest.mark.asyncio
    async def test_summarize_not_needed_returns_false(self, tracker):
        tracker.add_message("s5", "user", "short")
        result = await tracker.summarize_if_needed("s5", llm=None)
        assert result is False


# ---------------------------------------------------------------------------
# Conversational API endpoint tests
# ---------------------------------------------------------------------------


class TestConversationalAPI:
    def test_create_session(self, client):
        resp = client.post(
            "/api/v1/conversational/sessions",
            headers=H,
            json={"agent_name": "test_agent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data

    def test_list_sessions(self, client):
        resp = client.get("/api/v1/conversational/sessions", headers=H)
        assert resp.status_code == 200
        assert "sessions" in resp.json()

    def test_get_session(self, client):
        create = client.post(
            "/api/v1/conversational/sessions", headers=H, json={"agent_name": "agent1"}
        )
        sid = create.json()["session_id"]
        resp = client.get(f"/api/v1/conversational/sessions/{sid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid

    def test_get_missing_session_404(self, client):
        resp = client.get("/api/v1/conversational/sessions/nonexistent", headers=H)
        assert resp.status_code == 404

    def test_delete_session(self, client):
        create = client.post(
            "/api/v1/conversational/sessions",
            headers=H,
            json={"agent_name": "del_agent"},
        )
        sid = create.json()["session_id"]
        resp = client.delete(f"/api/v1/conversational/sessions/{sid}", headers=H)
        assert resp.status_code == 200

    def test_classify_intent(self, client):
        resp = client.post(
            "/api/v1/conversational/classify",
            headers=H,
            json={"text": "What is the weather today?"},
        )
        assert resp.status_code in (200, 503)
