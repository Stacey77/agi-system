"""API tests for the platform endpoints (tools, developer portal, Kally AI)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from src.api.main import create_app

    # The lifespan handler seeds app.state.tool_landscape / developer_portal /
    # kally_agent, so the endpoints resolve their dependencies.
    with TestClient(create_app()) as c:
        yield c


# ---------------------------------------------------------------------------
# Tooling landscape
# ---------------------------------------------------------------------------


class TestToolEndpoints:
    def test_list_tools(self, client):
        resp = client.get("/api/v1/platform/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == len(body["tools"])
        assert body["total"] > 0

    def test_list_tools_category_filter(self, client):
        resp = client.get("/api/v1/platform/tools", params={"category": "ai_ml"})
        assert resp.status_code == 200
        assert all(t["category"] == "ai_ml" for t in resp.json()["tools"])

    def test_list_tools_invalid_category(self, client):
        resp = client.get("/api/v1/platform/tools", params={"category": "bogus"})
        assert resp.status_code == 400
        assert "Unknown category" in resp.json()["detail"]

    def test_list_tools_invalid_tier(self, client):
        resp = client.get("/api/v1/platform/tools", params={"tier": "bogus"})
        assert resp.status_code == 400
        assert "Unknown tier" in resp.json()["detail"]

    def test_tools_summary(self, client):
        resp = client.get("/api/v1/platform/tools/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert sum(body["summary"].values()) == body["total"]

    def test_register_tool(self, client):
        resp = client.post(
            "/api/v1/platform/tools",
            json={"name": "MyTool", "category": "ci_cd", "tier": "internal"},
        )
        assert resp.status_code == 200
        tool = resp.json()["tool"]
        assert tool["name"] == "MyTool"
        assert tool["category"] == "ci_cd"
        assert tool["tier"] == "internal"

    def test_register_tool_invalid_category(self, client):
        resp = client.post(
            "/api/v1/platform/tools",
            json={"name": "Bad", "category": "nope"},
        )
        assert resp.status_code == 400
        assert "Unknown category" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Developer portal
# ---------------------------------------------------------------------------


class TestPortalEndpoints:
    def test_list_services(self, client):
        resp = client.get("/api/v1/platform/portal/services")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == len(body["services"])

    def test_list_services_invalid_tier(self, client):
        resp = client.get("/api/v1/platform/portal/services", params={"tier": "bogus"})
        assert resp.status_code == 400
        assert "Unknown tier" in resp.json()["detail"]

    def test_portal_health(self, client):
        resp = client.get("/api/v1/platform/portal/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status_counts" in body
        assert body["total_services"] == sum(body["status_counts"].values())

    def test_register_service(self, client):
        resp = client.post(
            "/api/v1/platform/portal/services",
            json={"name": "MyService", "tier": "external"},
        )
        assert resp.status_code == 200
        svc = resp.json()["service"]
        assert svc["name"] == "MyService"
        assert svc["tier"] == "external"
        assert svc["status"] == "operational"

    def test_register_service_invalid_tier(self, client):
        resp = client.post(
            "/api/v1/platform/portal/services",
            json={"name": "Bad", "tier": "nope"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Kally AI
# ---------------------------------------------------------------------------


class TestKallyEndpoints:
    def test_analyse(self, client):
        resp = client.post("/api/v1/platform/kally/analyse")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_ingest_signal_and_report(self, client):
        resp = client.post(
            "/api/v1/platform/kally/signals",
            json={
                "source": "api",
                "metric": "error_rate",
                "value": 0.2,
                "threshold": 0.1,
                "severity": "warning",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

        report = client.get("/api/v1/platform/kally/report")
        assert report.status_code == 200
        assert report.json()["buffered_signals"] >= 1

    def test_reset(self, client):
        client.post(
            "/api/v1/platform/kally/signals",
            json={"source": "x", "metric": "y", "value": 1.0},
        )
        resp = client.post("/api/v1/platform/kally/reset")
        assert resp.status_code == 200
        assert resp.json()["action"] == "reset"
