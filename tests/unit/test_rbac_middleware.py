"""Tests for RBAC + AuditLog wiring in auth middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


def _make_key(key_id: str = "k1"):
    """Return a mock API key. KeyRole only has 'admin', so we always use that."""
    from src.auth.key_store import KeyRole

    key = MagicMock()
    key.role = KeyRole("admin")
    key.key_id = key_id
    key.name = "test"
    return key


def _make_client(rbac_role: str | None = None):
    """Return (TestClient, app) with RBAC role optionally assigned to key k1."""
    from src.api.main import create_app
    from src.enterprise.rbac import RBACManager

    app = create_app()
    rbac = RBACManager()
    if rbac_role:
        rbac.assign_role("k1", rbac_role)

    client = TestClient(app, raise_server_exceptions=True)
    client.__enter__()
    app.state.key_store = MagicMock()
    app.state.key_store.list_keys.return_value = ["sk-test"]
    app.state.key_store.validate_key.return_value = _make_key()
    app.state.jwt_manager = MagicMock()
    app.state.jwt_manager.verify_token.return_value = None
    app.state.rbac_manager = rbac
    app.state.audit_log = None
    return client, app


HEADERS = {"X-API-Key": "sk-test"}


class TestRBACPermissions:
    def test_viewer_can_read_agents(self):
        client, _app = _make_client(rbac_role="viewer")
        try:
            resp = client.get("/api/v1/agents/", headers=HEADERS)
            assert resp.status_code not in (401, 403)
        finally:
            client.__exit__(None, None, None)

    def test_viewer_denied_delete_agent(self):
        client, _app = _make_client(rbac_role="viewer")
        try:
            resp = client.delete("/api/v1/agents/some-id", headers=HEADERS)
            assert resp.status_code == 403
        finally:
            client.__exit__(None, None, None)

    def test_viewer_denied_post_agents(self):
        client, _app = _make_client(rbac_role="viewer")
        try:
            resp = client.post("/api/v1/agents/", headers=HEADERS, json={})
            assert resp.status_code == 403
        finally:
            client.__exit__(None, None, None)

    def test_admin_can_delete_agent(self):
        client, _app = _make_client(rbac_role="admin")
        try:
            resp = client.delete("/api/v1/agents/some-id", headers=HEADERS)
            assert resp.status_code not in (401, 403)
        finally:
            client.__exit__(None, None, None)

    def test_admin_can_post_agents(self):
        client, _app = _make_client(rbac_role="admin")
        try:
            resp = client.post("/api/v1/agents/", headers=HEADERS, json={})
            assert resp.status_code not in (401, 403)
        finally:
            client.__exit__(None, None, None)


class TestDevModeBypass:
    def test_no_auth_required_in_dev_mode(self):
        from src.api.main import create_app

        app = create_app()
        with TestClient(app, raise_server_exceptions=True) as c:
            app.state.key_store = MagicMock()
            app.state.key_store.list_keys.return_value = []  # dev mode
            app.state.rbac_manager = None
            app.state.audit_log = None
            resp = c.get("/api/v1/agents/")
            assert resp.status_code not in (401, 403)

    def test_delete_allowed_without_key_in_dev_mode(self):
        from src.api.main import create_app

        app = create_app()
        with TestClient(app, raise_server_exceptions=True) as c:
            app.state.key_store = MagicMock()
            app.state.key_store.list_keys.return_value = []
            app.state.rbac_manager = None
            app.state.audit_log = None
            resp = c.delete("/api/v1/agents/x")
            assert resp.status_code not in (401, 403)


class TestNoRBACAssignment:
    def test_no_rbac_role_assigned_does_not_deny(self):
        """If RBAC has no role for the key_id, the RBAC check is skipped."""
        from src.api.main import create_app
        from src.enterprise.rbac import RBACManager

        app = create_app()
        rbac = RBACManager()
        # Intentionally NOT assigning any role to k1

        with TestClient(app, raise_server_exceptions=True) as c:
            app.state.key_store = MagicMock()
            app.state.key_store.list_keys.return_value = ["sk-test"]
            app.state.key_store.validate_key.return_value = _make_key()
            app.state.jwt_manager = MagicMock()
            app.state.jwt_manager.verify_token.return_value = None
            app.state.rbac_manager = rbac
            app.state.audit_log = None

            resp = c.delete("/api/v1/agents/x", headers=HEADERS)
            # No RBAC role assigned → check is skipped → not 403
            assert resp.status_code != 403


class TestAuditLogCalled:
    def test_audit_log_called_on_success_no_crash(self):
        """Audit log call via fire-and-forget should not raise."""
        client, app = _make_client(rbac_role="admin")
        try:
            mock_audit = MagicMock()
            mock_audit.log = AsyncMock(return_value="evt-1")
            app.state.audit_log = mock_audit
            resp = client.get("/api/v1/agents/", headers=HEADERS)
            assert resp.status_code not in (500,)
        finally:
            client.__exit__(None, None, None)

    def test_path_outside_resource_map_does_not_crash(self):
        """Paths that don't match the resource map fall back to 'system'."""
        client, _app = _make_client(rbac_role="admin")
        try:
            resp = client.get("/api/v1/scheduler/", headers=HEADERS)
            assert resp.status_code not in (500,)
        finally:
            client.__exit__(None, None, None)
