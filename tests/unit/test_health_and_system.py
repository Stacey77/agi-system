"""Tests for enhanced health check, request-ID middleware, and system info."""

from __future__ import annotations

import pytest


class TestHealthEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        with TestClient(create_app()) as c:
            yield c

    def test_liveness(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_detailed_health_structure(self, client):
        r = client.get("/health/detailed")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "components" in data
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_detailed_health_has_components(self, client):
        r = client.get("/health/detailed")
        comps = r.json()["components"]
        assert "task_queue" in comps
        assert "llm" in comps
        assert "agent_factory" in comps
        assert "auth" in comps

    def test_detailed_health_overall_status(self, client):
        r = client.get("/health/detailed")
        assert r.json()["status"] in ("healthy", "degraded")


class TestRequestIDMiddleware:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        with TestClient(create_app()) as c:
            yield c

    def test_response_has_request_id(self, client):
        r = client.get("/health")
        assert "x-request-id" in r.headers

    def test_request_id_is_uuid(self, client):
        import uuid
        r = client.get("/health")
        rid = r.headers.get("x-request-id", "")
        uuid.UUID(rid)  # raises if not valid UUID

    def test_custom_request_id_echoed(self, client):
        r = client.get("/health", headers={"X-Request-ID": "my-trace-id-123"})
        assert r.headers.get("x-request-id") == "my-trace-id-123"

    def test_different_requests_get_different_ids(self, client):
        r1 = client.get("/health")
        r2 = client.get("/health")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


class TestSystemInfo:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        with TestClient(create_app()) as c:
            yield c

    def test_system_info_structure(self, client):
        r = client.get("/api/v1/system/info")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "python" in data
        assert "uptime_seconds" in data
        assert "agents" in data
        assert "tools" in data

    def test_system_info_agents_populated(self, client):
        r = client.get("/api/v1/system/info")
        agents = r.json()["agents"]
        assert isinstance(agents, list)
        assert len(agents) > 0

    def test_system_info_tools_populated(self, client):
        r = client.get("/api/v1/system/info")
        tools = r.json()["tools"]
        assert isinstance(tools, list)
