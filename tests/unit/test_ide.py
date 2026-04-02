"""Unit tests for the vibecoding IDE module."""

from __future__ import annotations

import pytest

from src.agents.base_agent import AgentConfig, AgentType
from src.ide.ide_agent import IDEAgent
from src.ide.ide_session import IDESession, IDESessionManager, SessionState


# ---------------------------------------------------------------------------
# IDESession
# ---------------------------------------------------------------------------

class TestIDESession:
    def test_initial_state(self):
        session = IDESession(language="python")
        assert session.state == SessionState.ACTIVE
        assert session.language == "python"
        assert len(session.history) == 0

    def test_add_interaction(self):
        session = IDESession()
        session.add_interaction("user", "hello")
        assert len(session.history) == 1
        assert session.history[0]["role"] == "user"

    def test_close(self):
        session = IDESession()
        session.close()
        assert session.state == SessionState.CLOSED

    def test_to_dict(self):
        session = IDESession(language="javascript")
        d = session.to_dict()
        assert d["language"] == "javascript"
        assert "session_id" in d
        assert "state" in d


# ---------------------------------------------------------------------------
# IDESessionManager
# ---------------------------------------------------------------------------

class TestIDESessionManager:
    def test_create_and_retrieve(self):
        mgr = IDESessionManager()
        session = mgr.create_session(language="python")
        assert mgr.get_session(session.session_id) is session

    def test_close_session(self):
        mgr = IDESessionManager()
        session = mgr.create_session()
        closed = mgr.close_session(session.session_id)
        assert closed is True
        assert session.state == SessionState.CLOSED

    def test_close_nonexistent(self):
        mgr = IDESessionManager()
        assert mgr.close_session("does-not-exist") is False

    def test_list_sessions(self):
        mgr = IDESessionManager()
        mgr.create_session()
        mgr.create_session()
        assert len(mgr.list_sessions()) == 2

    def test_active_count(self):
        mgr = IDESessionManager()
        s1 = mgr.create_session()
        s2 = mgr.create_session()
        mgr.close_session(s1.session_id)
        assert mgr.active_count() == 1


# ---------------------------------------------------------------------------
# IDEAgent
# ---------------------------------------------------------------------------

class TestIDEAgent:
    def _make_agent(self) -> IDEAgent:
        config = AgentConfig(name="ide", agent_type=AgentType.IDE)
        return IDEAgent(config)

    @pytest.mark.asyncio
    async def test_complete_code(self):
        agent = self._make_agent()
        result = await agent.complete_code("sort a list", language="python")
        assert result.language == "python"
        assert result.action == "complete"
        assert len(result.completion) > 0
        assert 0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_explain_code(self):
        agent = self._make_agent()
        result = await agent.explain_code("for i in range(10): print(i)", language="python")
        assert result.action == "explain"
        assert len(result.completion) > 0

    @pytest.mark.asyncio
    async def test_refactor_code(self):
        agent = self._make_agent()
        result = await agent.refactor_code("x=1\ny=2\nz=x+y", language="python")
        assert result.action == "refactor"

    @pytest.mark.asyncio
    async def test_fix_code(self):
        agent = self._make_agent()
        result = await agent.fix_code("def f():\n  return x", language="python")
        assert result.action == "fix"

    @pytest.mark.asyncio
    async def test_generate_code(self):
        agent = self._make_agent()
        result = await agent.generate_code("a function that reverses a string", language="python")
        assert result.action == "generate"
        assert "solution" in result.completion.lower() or "TODO" in result.completion

    @pytest.mark.asyncio
    async def test_review_code(self):
        agent = self._make_agent()
        result = await agent.review_code("def f(): pass", language="python")
        assert result.action == "review"
        assert len(result.completion) > 0

    @pytest.mark.asyncio
    async def test_process_task_dispatches(self):
        agent = self._make_agent()
        result = await agent.process_task({"action": "complete", "prompt": "hello world", "language": "python"})
        assert result["status"] == "completed"
        assert result["action"] == "complete"
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_session_reuse(self):
        agent = self._make_agent()
        result1 = await agent.process_task({"action": "complete", "prompt": "foo", "language": "python"})
        sid = result1["session_id"]
        result2 = await agent.process_task({"action": "explain", "prompt": "bar", "session_id": sid})
        assert result2["session_id"] == sid

    @pytest.mark.asyncio
    async def test_javascript_skeleton(self):
        agent = self._make_agent()
        result = await agent.generate_code("add two numbers", language="javascript")
        assert "function" in result.completion

    @pytest.mark.asyncio
    async def test_suggestions_present(self):
        agent = self._make_agent()
        result = await agent.complete_code("binary search", language="python")
        assert len(result.suggestions) > 0
