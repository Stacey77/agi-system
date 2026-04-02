"""Integration tests — end-to-end workflows via the FastAPI TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as c:
        yield c


class TestHealthEndpoints:
    def test_basic_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_detailed_health(self, client):
        response = client.get("/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data


class TestAgentEndpoints:
    def test_list_agents(self, client):
        response = client.get("/api/v1/agents/")
        assert response.status_code == 200
        agents = response.json()
        assert isinstance(agents, list)
        assert len(agents) > 0
        names = [a["name"] for a in agents]
        assert "planning_agent" in names

    def test_agent_status(self, client):
        response = client.get("/api/v1/agents/research_agent/status")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "type" in data

    def test_agent_execute(self, client):
        response = client.post(
            "/api/v1/agents/research_agent/execute",
            json={"task": "Find information about Python"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

    def test_unknown_agent_returns_404(self, client):
        response = client.get("/api/v1/agents/unknown_agent/status")
        assert response.status_code == 404


class TestTaskEndpoints:
    def test_submit_and_retrieve_task(self, client):
        # Submit
        response = client.post(
            "/api/v1/tasks/",
            json={"objective": "Research AI trends"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        task_id = data["task_id"]

        # Retrieve
        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        task_data = response.json()
        assert task_data["task_id"] == task_id

    def test_cancel_task(self, client):
        # Submit first
        response = client.post(
            "/api/v1/tasks/",
            json={"objective": "A cancellable task"},
        )
        task_id = response.json()["task_id"]

        # The task may be completed already in test mode; just verify the endpoint works
        cancel_response = client.delete(f"/api/v1/tasks/{task_id}")
        assert cancel_response.status_code == 200

    def test_unknown_task_returns_404(self, client):
        response = client.get("/api/v1/tasks/nonexistent-task-id")
        assert response.status_code == 404


class TestCrewEndpoints:
    def test_list_crew_agents(self, client):
        response = client.get("/api/v1/crews/agents")
        assert response.status_code == 200
        agents = response.json()
        assert isinstance(agents, list)
        assert len(agents) > 0

    def test_run_crew(self, client):
        response = client.post(
            "/api/v1/crews/run",
            json={"objective": "Research and summarize AI trends"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "output" in data
        assert data["objective"] == "Research and summarize AI trends"

    def test_run_crew_with_explicit_tasks(self, client):
        response = client.post(
            "/api/v1/crews/run",
            json={
                "objective": "Build a report",
                "agent_names": ["research_agent", "writing_agent"],
                "tasks": [
                    {"description": "Gather data on AI"},
                    {"description": "Draft a report"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["task_outputs"]) == 2

