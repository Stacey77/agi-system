"""Tests for crew templates, runtime agent registration, agent history, and token tracker wiring."""

from __future__ import annotations

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
# Crew templates
# ---------------------------------------------------------------------------

class TestCrewTemplates:
    def test_create_template(self, client):
        resp = client.post("/api/v1/crew/templates", headers=H, json={
            "name": "research_brief",
            "description": "Research then write",
            "agent_names": ["research_agent", "writing_agent"],
            "max_iterations": 2,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "research_brief"
        assert data["agent_names"] == ["research_agent", "writing_agent"]

    def test_create_duplicate_template_409(self, client):
        client.post("/api/v1/crew/templates", headers=H, json={
            "name": "dup_template",
            "agent_names": ["research_agent"],
        })
        resp = client.post("/api/v1/crew/templates", headers=H, json={
            "name": "dup_template",
            "agent_names": ["research_agent"],
        })
        assert resp.status_code == 409

    def test_list_templates(self, client):
        resp = client.get("/api/v1/crew/templates", headers=H)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        names = [t["name"] for t in resp.json()]
        assert "research_brief" in names

    def test_get_template(self, client):
        resp = client.get("/api/v1/crew/templates/research_brief", headers=H)
        assert resp.status_code == 200
        assert resp.json()["name"] == "research_brief"

    def test_get_missing_template_404(self, client):
        resp = client.get("/api/v1/crew/templates/nonexistent", headers=H)
        assert resp.status_code == 404

    def test_delete_template(self, client):
        client.post("/api/v1/crew/templates", headers=H, json={
            "name": "to_delete",
            "agent_names": ["review_agent"],
        })
        resp = client.delete("/api/v1/crew/templates/to_delete", headers=H)
        assert resp.status_code in (200, 204)
        resp2 = client.get("/api/v1/crew/templates/to_delete", headers=H)
        assert resp2.status_code == 404


# ---------------------------------------------------------------------------
# Runtime agent registration
# ---------------------------------------------------------------------------

class TestRuntimeAgentRegistration:
    def test_create_agent(self, client):
        resp = client.post("/api/v1/agents/", headers=H, json={
            "name": "dynamic_agent",
            "agent_type": "research",
            "description": "Dynamically registered",
            "capabilities": ["web_search"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "dynamic_agent"

    def test_create_duplicate_agent_409(self, client):
        client.post("/api/v1/agents/", headers=H, json={
            "name": "dup_agent",
            "agent_type": "analysis",
        })
        resp = client.post("/api/v1/agents/", headers=H, json={
            "name": "dup_agent",
            "agent_type": "analysis",
        })
        assert resp.status_code == 409

    def test_create_invalid_type_422(self, client):
        resp = client.post("/api/v1/agents/", headers=H, json={
            "name": "bad_agent",
            "agent_type": "not_a_real_type",
        })
        assert resp.status_code == 422

    def test_delete_agent(self, client):
        client.post("/api/v1/agents/", headers=H, json={
            "name": "agent_to_delete",
            "agent_type": "review",
        })
        resp = client.delete("/api/v1/agents/agent_to_delete", headers=H)
        assert resp.status_code in (200, 204)

    def test_delete_protected_agent_409(self, client):
        resp = client.delete("/api/v1/agents/planning_agent", headers=H)
        assert resp.status_code == 409

    def test_delete_nonexistent_agent_404(self, client):
        resp = client.delete("/api/v1/agents/nonexistent_xyz", headers=H)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Agent history endpoint
# ---------------------------------------------------------------------------

class TestAgentHistory:
    def test_history_shape(self, client):
        resp = client.get("/api/v1/agents/planning_agent/history", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_name" in data
        assert "total_calls" in data
        assert "total_tokens" in data
        assert "records" in data
        assert isinstance(data["records"], list)

    def test_history_limit(self, client):
        resp = client.get("/api/v1/agents/planning_agent/history",
                          headers=H, params={"limit": 5})
        assert resp.status_code == 200
        assert len(resp.json()["records"]) <= 5

    def test_history_unknown_agent(self, client):
        resp = client.get("/api/v1/agents/unknown_xyz/history", headers=H)
        # 404 when agent doesn't exist, or 200 with empty records — both valid
        assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Token tracker wiring into agents
# ---------------------------------------------------------------------------

class TestTokenTrackerWiring:
    def test_factory_set_token_tracker(self):
        from src.agents.agent_factory import AgentFactory
        from src.execution.execution_agent import ExecutionAgent
        from src.execution.execution_engine import ExecutionEngine
        from src.llm.token_tracker import TokenTracker

        engine = ExecutionEngine()
        exec_agent = ExecutionAgent(execution_engine=engine)
        factory = AgentFactory(execution_agent=exec_agent)
        tracker = TokenTracker()
        factory.set_token_tracker(tracker)

        for name in factory.list_agents():
            agent = factory.get_agent(name)
            if agent is not None:
                assert agent._tracker is tracker

    def test_base_agent_set_token_tracker(self):
        from src.agents.base_agent import AgentConfig, AgentType
        from src.agents.research_agent import ResearchAgent
        from src.execution.execution_agent import ExecutionAgent
        from src.execution.execution_engine import ExecutionEngine
        from src.llm.token_tracker import TokenTracker

        engine = ExecutionEngine()
        exec_agent = ExecutionAgent(execution_engine=engine)
        cfg = AgentConfig(name="t", agent_type=AgentType.RESEARCH, description="test")
        agent = ResearchAgent(config=cfg, execution_agent=exec_agent)
        tracker = TokenTracker()
        agent.set_token_tracker(tracker)
        assert agent._tracker is tracker
