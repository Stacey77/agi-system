"""Integration tests for crew endpoint and WebSocket streaming."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as c:
        yield c


class TestCrewEndpoints:
    def test_crew_run_returns_result(self, client):
        response = client.post(
            "/api/v1/crew/run",
            json={"objective": "Summarise recent AI developments"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "result" in data
        assert "objective" in data

    def test_crew_run_with_specific_agents(self, client):
        response = client.post(
            "/api/v1/crew/run",
            json={
                "objective": "Analyse market trends",
                "agents": ["research_agent", "analysis_agent"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert set(data["agents_used"]) == {"research_agent", "analysis_agent"}

    def test_crew_run_stream_returns_sse(self, client):
        response = client.post(
            "/api/v1/crew/run/stream",
            json={
                "objective": "Write a short report",
                "agents": ["writing_agent"],
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "data:" in body
        assert "[DONE]" in body

    def test_crew_stream_includes_agent_name(self, client):
        response = client.post(
            "/api/v1/crew/run/stream",
            json={
                "objective": "Research topic X",
                "agents": ["research_agent"],
            },
        )
        body = response.text
        lines = [ln for ln in body.splitlines() if ln.startswith("data:") and "[DONE]" not in ln]
        if lines:
            payload = json.loads(lines[0][len("data:"):].strip())
            assert "agent" in payload

    def test_crew_run_no_orchestrator_returns_503(self, client):
        # Temporarily remove orchestrator from app state
        original = client.app.state.crew_orchestrator
        del client.app.state.crew_orchestrator
        try:
            response = client.post(
                "/api/v1/crew/run",
                json={"objective": "anything"},
            )
            assert response.status_code == 503
        finally:
            client.app.state.crew_orchestrator = original


class TestWebSocketEndpoint:
    def test_websocket_streams_response(self, client):
        with client.websocket_connect("/api/v1/agents/research_agent/ws") as ws:
            ws.send_json({"task": "Tell me about Python", "parameters": {}})
            messages = []
            while True:
                msg = ws.receive_text()
                messages.append(msg)
                if msg == "[DONE]":
                    break
            assert "[DONE]" in messages
            assert len(messages) >= 1

    def test_websocket_unknown_agent_closes_with_error(self, client):
        with client.websocket_connect("/api/v1/agents/unknown_agent/ws") as ws:
            data = ws.receive_json()
            assert "error" in data

    def test_websocket_writing_agent(self, client):
        with client.websocket_connect("/api/v1/agents/writing_agent/ws") as ws:
            ws.send_json({"task": "Write a haiku about Python"})
            chunks = []
            while True:
                msg = ws.receive_text()
                if msg == "[DONE]":
                    break
                chunks.append(msg)
            assert len(chunks) >= 1

    def test_websocket_coding_agent(self, client):
        with client.websocket_connect("/api/v1/agents/coding_agent/ws") as ws:
            ws.send_json({"task": "Write a hello world function in Python"})
            messages = []
            while True:
                msg = ws.receive_text()
                messages.append(msg)
                if msg == "[DONE]":
                    break
        assert "[DONE]" in messages


class TestAgentMemoryEndpoint:
    def test_memory_recall_returns_results(self, client):
        response = client.get(
            "/api/v1/agents/research_agent/memory",
            params={"query": "Python programming", "k": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "research_agent"
        assert data["query"] == "Python programming"
        assert isinstance(data["results"], list)

    def test_memory_recall_unknown_agent_404(self, client):
        response = client.get(
            "/api/v1/agents/nonexistent/memory",
            params={"query": "anything"},
        )
        assert response.status_code == 404
