"""Integration tests — agent workflow scenarios via FastAPI TestClient."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.auth.key_store import KeyRole


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create the app and inject a test API key so auth middleware lets us through."""
    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as c:
        # The auth middleware skips validation when no keys are registered.
        # If keys ARE registered (e.g. via env), create one we control so tests
        # always have a valid credential.
        key_store = getattr(c.app.state, "key_store", None)
        raw_key = None
        if key_store is not None:
            raw_key, _ = key_store.create_key("test-integration", KeyRole.ADMIN)
        c._test_api_key = raw_key
        yield c


@pytest.fixture(scope="module")
def auth_headers(client: TestClient):
    """Return headers dict with X-API-Key when one was created."""
    key = getattr(client, "_test_api_key", None)
    if key:
        return {"X-API-Key": key}
    return {}


# ---------------------------------------------------------------------------
# 1. Planning agent delegation
# ---------------------------------------------------------------------------


class TestPlanningAgentDelegation:
    def test_planning_agent_returns_plan_structure(self, client, auth_headers):
        response = client.post(
            "/api/v1/agents/planning_agent/execute",
            json={"task": "Build a simple web scraper"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        result = data["result"]
        assert result["status"] == "completed"
        plan = result["plan"]
        assert "objective" in plan
        assert "steps" in plan
        assert isinstance(plan["steps"], list)
        assert len(plan["steps"]) > 0
        assert "dependencies" in plan
        assert "is_valid" in plan

    def test_planning_agent_step_has_required_fields(self, client, auth_headers):
        response = client.post(
            "/api/v1/agents/planning_agent/execute",
            json={"task": "Analyse sentiment of customer reviews"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        steps = response.json()["result"]["plan"]["steps"]
        for step in steps:
            assert "step_id" in step


# ---------------------------------------------------------------------------
# 2. Memory round-trip
# ---------------------------------------------------------------------------


class TestMemoryRoundTrip:
    def test_store_and_retrieve_short_term_memory(self, client, auth_headers):
        key = "integration_test_key"
        value = "integration_test_value_42"

        # Store
        store_resp = client.post(
            "/api/v1/memory/store",
            json={"key": key, "value": value, "memory_type": "short_term"},
            headers=auth_headers,
        )
        assert store_resp.status_code == 200

        # Retrieve
        retrieve_resp = client.get(
            "/api/v1/memory/retrieve",
            params={"key": key, "memory_type": "short_term"},
            headers=auth_headers,
        )
        assert retrieve_resp.status_code == 200
        data = retrieve_resp.json()
        assert data["key"] == key
        assert data["value"] == value
        assert data["memory_type"] == "short_term"

    def test_retrieve_nonexistent_key_returns_none(self, client, auth_headers):
        retrieve_resp = client.get(
            "/api/v1/memory/retrieve",
            params={"key": "definitely_does_not_exist_xyz", "memory_type": "short_term"},
            headers=auth_headers,
        )
        assert retrieve_resp.status_code == 200
        data = retrieve_resp.json()
        assert data["value"] is None


# ---------------------------------------------------------------------------
# 3. Task lifecycle — queued → completed
# ---------------------------------------------------------------------------


class TestTaskLifecycle:
    def test_task_transitions_to_completed(self, client, auth_headers):
        # Submit
        submit_resp = client.post(
            "/api/v1/tasks/",
            json={"objective": "Summarise the history of the internet"},
            headers=auth_headers,
        )
        assert submit_resp.status_code == 200
        task_id = submit_resp.json()["task_id"]

        # Poll until completed or 3 s timeout
        deadline = time.time() + 3.0
        status = None
        seen_queued = False
        while time.time() < deadline:
            poll_resp = client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
            assert poll_resp.status_code == 200
            status = poll_resp.json()["status"]
            if status in ("queued", "running"):
                seen_queued = True
            if status == "completed":
                break
            time.sleep(0.1)

        assert status == "completed", f"Task did not complete in time; last status={status!r}"

    def test_submitted_task_has_task_id(self, client, auth_headers):
        resp = client.post(
            "/api/v1/tasks/",
            json={"objective": "Quick test task"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "task_id" in resp.json()


# ---------------------------------------------------------------------------
# 4. Agent circuit breaker state
# ---------------------------------------------------------------------------


class TestAgentCircuitBreakerState:
    def test_agent_status_has_circuit_breaker_fields(self, client, auth_headers):
        response = client.get(
            "/api/v1/agents/planning_agent/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "consecutive_failures" in data
        assert "circuit_open" in data
        assert isinstance(data["consecutive_failures"], int)
        assert isinstance(data["circuit_open"], bool)

    def test_circuit_breaker_defaults_to_closed(self, client, auth_headers):
        response = client.get(
            "/api/v1/agents/research_agent/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["circuit_open"] is False
        assert data["consecutive_failures"] == 0


# ---------------------------------------------------------------------------
# 5. Webhook registration and listing
# ---------------------------------------------------------------------------


class TestWebhookRegistrationAndListing:
    def test_register_list_and_delete_webhook(self, client, auth_headers):
        # Register
        reg_resp = client.post(
            "/api/v1/webhooks/",
            json={"url": "https://example.com/hook", "events": ["task.completed"]},
            headers=auth_headers,
        )
        assert reg_resp.status_code == 201
        reg_data = reg_resp.json()
        assert "webhook_id" in reg_data
        webhook_id = reg_data["webhook_id"]
        assert reg_data["url"] == "https://example.com/hook"
        assert "task.completed" in reg_data["events"]

        # List — the registered webhook must appear
        list_resp = client.get("/api/v1/webhooks/", headers=auth_headers)
        assert list_resp.status_code == 200
        webhooks = list_resp.json()
        ids = [w["id"] for w in webhooks]
        assert webhook_id in ids

        # Delete
        del_resp = client.delete(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)
        assert del_resp.status_code == 200

        # Confirm deletion
        list_resp2 = client.get("/api/v1/webhooks/", headers=auth_headers)
        ids_after = [w["id"] for w in list_resp2.json()]
        assert webhook_id not in ids_after

    def test_delete_nonexistent_webhook_returns_404(self, client, auth_headers):
        resp = client.delete("/api/v1/webhooks/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. Schedule lifecycle — create / list / pause / resume / delete
# ---------------------------------------------------------------------------


class TestScheduleLifecycle:
    def test_full_schedule_lifecycle(self, client, auth_headers):
        # Create
        create_resp = client.post(
            "/api/v1/schedules/",
            json={
                "objective": "Run daily report",
                "interval_seconds": 60,
                "run_immediately": False,
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 200
        sched = create_resp.json()
        assert "schedule_id" in sched
        schedule_id = sched["schedule_id"]
        assert sched["enabled"] is True

        # List — schedule appears
        list_resp = client.get("/api/v1/schedules/", headers=auth_headers)
        assert list_resp.status_code == 200
        ids = [s["schedule_id"] for s in list_resp.json()]
        assert schedule_id in ids

        # Pause
        pause_resp = client.post(
            f"/api/v1/schedules/{schedule_id}/pause",
            headers=auth_headers,
        )
        assert pause_resp.status_code == 200
        assert pause_resp.json()["enabled"] is False

        # Resume
        resume_resp = client.post(
            f"/api/v1/schedules/{schedule_id}/resume",
            headers=auth_headers,
        )
        assert resume_resp.status_code == 200
        assert resume_resp.json()["enabled"] is True

        # Delete
        del_resp = client.delete(f"/api/v1/schedules/{schedule_id}", headers=auth_headers)
        assert del_resp.status_code == 200

        # Confirm deletion
        list_resp2 = client.get("/api/v1/schedules/", headers=auth_headers)
        ids_after = [s["schedule_id"] for s in list_resp2.json()]
        assert schedule_id not in ids_after


# ---------------------------------------------------------------------------
# 7. Usage tracking
# ---------------------------------------------------------------------------


class TestUsageTracking:
    def test_usage_endpoint_returns_expected_shape(self, client, auth_headers):
        response = client.get("/api/v1/usage/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_tokens" in data
        assert "by_agent" in data
        assert "total_calls" in data
        assert isinstance(data["total_tokens"], int)
        assert isinstance(data["by_agent"], dict)
        assert isinstance(data["total_calls"], int)


# ---------------------------------------------------------------------------
# 8. Session create and message
# ---------------------------------------------------------------------------


class TestSessionCreateAndMessage:
    def test_create_session_send_message_and_retrieve(self, client, auth_headers):
        # Create a session with the writing agent
        create_resp = client.post(
            "/api/v1/sessions/",
            json={"agent_name": "writing_agent"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        session_data = create_resp.json()
        assert "session_id" in session_data
        session_id = session_data["session_id"]
        assert session_data["agent_name"] == "writing_agent"

        # Send a message
        msg_resp = client.post(
            f"/api/v1/sessions/{session_id}/message",
            json={"message": "Write a one-sentence summary of Python."},
            headers=auth_headers,
        )
        assert msg_resp.status_code == 200
        msg_data = msg_resp.json()
        assert msg_data["role"] == "assistant"
        assert isinstance(msg_data["content"], str)
        assert len(msg_data["content"]) > 0

        # Retrieve history — message should appear
        history_resp = client.get(
            f"/api/v1/sessions/{session_id}/history",
            headers=auth_headers,
        )
        assert history_resp.status_code == 200
        messages = history_resp.json()
        assert isinstance(messages, list)
        assert len(messages) >= 2  # user message + assistant response
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_get_nonexistent_session_returns_404(self, client, auth_headers):
        resp = client.get(
            "/api/v1/sessions/nonexistent-session-id",
            headers=auth_headers,
        )
        assert resp.status_code == 404
