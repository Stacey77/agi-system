"""Unit tests for enterprise package (audit log, RBAC, tenants) and API endpoints."""

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
# AuditLog unit tests
# ---------------------------------------------------------------------------


class TestAuditLog:
    @pytest.fixture()
    def audit(self, tmp_path):
        from src.enterprise.audit_log import AuditLog

        return AuditLog(db_path=str(tmp_path / "audit_test.db"))

    @pytest.mark.asyncio
    async def test_log_event(self, audit):
        eid = await audit.log(actor="user1", action="create", resource_type="agent")
        assert isinstance(eid, str)
        assert len(eid) > 0

    @pytest.mark.asyncio
    async def test_get_event(self, audit):
        eid = await audit.log(
            actor="alice", action="delete", resource_type="task", resource_id="t1"
        )
        event = await audit.get_event(eid)
        assert event is not None
        assert event["event_id"] == eid
        assert event["actor"] == "alice"

    @pytest.mark.asyncio
    async def test_get_missing_event_returns_none(self, audit):
        result = await audit.get_event("no-such-event")
        assert result is None

    @pytest.mark.asyncio
    async def test_query_by_actor(self, audit):
        await audit.log(actor="bob", action="read", resource_type="memory")
        await audit.log(actor="bob", action="write", resource_type="memory")
        await audit.log(actor="carol", action="read", resource_type="memory")
        result = await audit.query(actor="bob")
        assert result["total"] >= 2
        for ev in result["events"]:
            assert ev["actor"] == "bob"

    @pytest.mark.asyncio
    async def test_query_by_action(self, audit):
        await audit.log(actor="x", action="special_action", resource_type="r")
        result = await audit.query(action="special_action")
        assert result["total"] >= 1

    @pytest.mark.asyncio
    async def test_query_pagination(self, audit):
        for _ in range(5):
            await audit.log(
                actor="paginate_user", action="view", resource_type="dashboard"
            )
        page1 = await audit.query(actor="paginate_user", limit=2, offset=0)
        page2 = await audit.query(actor="paginate_user", limit=2, offset=2)
        assert len(page1["events"]) == 2
        assert page1["total"] >= 5
        assert page2["events"][0]["event_id"] != page1["events"][0]["event_id"]

    @pytest.mark.asyncio
    async def test_purge_before(self, audit):
        import time

        await audit.log(actor="old_actor", action="old_action", resource_type="r")
        n = await audit.purge_before(time.time() + 1)
        assert n >= 1

    @pytest.mark.asyncio
    async def test_details_serialized(self, audit):
        eid = await audit.log(
            actor="sys",
            action="deploy",
            resource_type="service",
            details={"version": "1.0", "region": "us-east-1"},
        )
        event = await audit.get_event(eid)
        assert event["details"]["version"] == "1.0"


# ---------------------------------------------------------------------------
# RBACManager unit tests
# ---------------------------------------------------------------------------


class TestRBACManager:
    @pytest.fixture()
    def rbac(self):
        from src.enterprise.rbac import RBACManager

        return RBACManager()

    def test_default_roles_seeded(self, rbac):
        roles = rbac.list_roles()
        names = [r.name for r in roles]
        assert "super_admin" in names
        assert "admin" in names
        assert "operator" in names
        assert "viewer" in names

    def test_default_permissions_seeded(self, rbac):
        perms = rbac.list_permissions()
        assert len(perms) >= 10

    def test_super_admin_has_wildcard(self, rbac):
        role = rbac.get_role("super_admin")
        assert role.has_permission("any:arbitrary:permission")

    def test_viewer_cannot_write(self, rbac):
        role = rbac.get_role("viewer")
        assert not role.has_permission("agents:write")

    def test_create_role(self, rbac):
        role = rbac.create_role(
            "custom_role", permissions=["tasks:read"], description="Custom"
        )
        assert rbac.get_role("custom_role") is role
        assert "tasks:read" in role.permissions

    def test_delete_role(self, rbac):
        rbac.create_role("temp_role")
        assert rbac.delete_role("temp_role") is True
        assert rbac.get_role("temp_role") is None

    def test_delete_missing_role_returns_false(self, rbac):
        assert rbac.delete_role("no_such_role") is False

    def test_assign_and_check_permission(self, rbac):
        rbac.assign_role("user1", "operator")
        assert rbac.check_permission("user1", "tasks:read") is True

    def test_check_permission_without_role_returns_false(self, rbac):
        assert rbac.check_permission("orphan_user", "agents:read") is False

    def test_revoke_role(self, rbac):
        rbac.assign_role("user2", "operator")
        rbac.revoke_role("user2", "operator")
        assert rbac.check_permission("user2", "tasks:read") is False

    def test_add_permission_to_role(self, rbac):
        rbac.create_role("extendable", permissions=[])
        rbac.add_permission_to_role("extendable", "tasks:read")
        role = rbac.get_role("extendable")
        assert "tasks:read" in role.permissions

    def test_remove_permission_from_role(self, rbac):
        rbac.create_role("shrinkable", permissions=["tasks:read", "agents:read"])
        rbac.remove_permission_from_role("shrinkable", "tasks:read")
        role = rbac.get_role("shrinkable")
        assert "tasks:read" not in role.permissions

    def test_get_user_permissions_aggregated(self, rbac):
        rbac.create_role("role_a", permissions=["tasks:read"])
        rbac.create_role("role_b", permissions=["agents:read"])
        rbac.assign_role("multi_user", "role_a")
        rbac.assign_role("multi_user", "role_b")
        perms = rbac.get_user_permissions("multi_user")
        assert "tasks:read" in perms
        assert "agents:read" in perms


# ---------------------------------------------------------------------------
# TenantManager unit tests
# ---------------------------------------------------------------------------


class TestTenantManager:
    @pytest.fixture()
    def tm(self):
        from src.enterprise.tenant_manager import TenantManager

        return TenantManager()

    def test_create_tenant(self, tm):
        tenant = tm.create_tenant("Acme Corp", plan="starter")
        assert tenant.name == "Acme Corp"
        assert tenant.plan == "starter"
        assert tenant.active is True

    def test_get_tenant(self, tm):
        t = tm.create_tenant("GetMe")
        fetched = tm.get_tenant(t.tenant_id)
        assert fetched is t

    def test_get_missing_tenant_returns_none(self, tm):
        assert tm.get_tenant("no-such-id") is None

    def test_list_tenants(self, tm):
        tm.create_tenant("T1")
        tm.create_tenant("T2")
        tenants = tm.list_tenants()
        assert len(tenants) >= 2

    def test_list_tenants_active_only(self, tm):
        t = tm.create_tenant("InactiveTenant")
        tm.update_tenant(t.tenant_id, active=False)
        active = tm.list_tenants(active_only=True)
        assert not any(x.tenant_id == t.tenant_id for x in active)

    def test_update_tenant_name(self, tm):
        t = tm.create_tenant("OldName")
        updated = tm.update_tenant(t.tenant_id, name="NewName")
        assert updated.name == "NewName"

    def test_update_tenant_plan(self, tm):
        t = tm.create_tenant("UpgradeTenant", plan="free")
        updated = tm.update_tenant(t.tenant_id, plan="pro")
        assert updated.plan == "pro"

    def test_update_missing_tenant_returns_none(self, tm):
        assert tm.update_tenant("bad-id", name="x") is None

    def test_update_invalid_plan_raises(self, tm):
        t = tm.create_tenant("ValidTenant")
        with pytest.raises(ValueError):
            tm.update_tenant(t.tenant_id, plan="ultra_premium")

    def test_delete_tenant(self, tm):
        t = tm.create_tenant("DeleteMe")
        assert tm.delete_tenant(t.tenant_id) is True
        assert tm.get_tenant(t.tenant_id) is None

    def test_delete_missing_tenant_returns_false(self, tm):
        assert tm.delete_tenant("no-such-id") is False

    def test_plan_limits(self, tm):
        t = tm.create_tenant("FreeTenant", plan="free")
        assert t.limits["agents"] == 3
        t2 = tm.create_tenant("EnterpriseTenant", plan="enterprise")
        assert t2.limits["agents"] == -1

    def test_create_invalid_plan_raises(self, tm):
        with pytest.raises(ValueError):
            tm.create_tenant("BadPlan", plan="unknown_plan")

    def test_to_dict_keys(self, tm):
        t = tm.create_tenant("DictTenant", plan="pro")
        d = t.to_dict()
        assert "tenant_id" in d
        assert "limits" in d
        assert d["plan"] == "pro"


# ---------------------------------------------------------------------------
# Enterprise API endpoint tests
# ---------------------------------------------------------------------------


class TestEnterpriseAPI:
    def test_list_audit_events(self, client):
        resp = client.get("/api/v1/enterprise/audit/events", headers=H)
        assert resp.status_code == 200
        assert "events" in resp.json()

    def test_list_roles(self, client):
        resp = client.get("/api/v1/enterprise/rbac/roles", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert "roles" in data
        names = [r["name"] for r in data["roles"]]
        assert "admin" in names

    def test_create_role(self, client):
        resp = client.post(
            "/api/v1/enterprise/rbac/roles",
            headers=H,
            json={"name": "api_test_role", "permissions": ["tasks:read"]},
        )
        assert resp.status_code == 200

    def test_list_tenants(self, client):
        resp = client.get("/api/v1/enterprise/tenants", headers=H)
        assert resp.status_code == 200
        assert "tenants" in resp.json()

    def test_create_tenant(self, client):
        resp = client.post(
            "/api/v1/enterprise/tenants",
            headers=H,
            json={"name": "API Test Tenant", "plan": "starter"},
        )
        assert resp.status_code == 200
        assert "tenant_id" in resp.json()

    def test_get_tenant(self, client):
        create = client.post(
            "/api/v1/enterprise/tenants",
            headers=H,
            json={"name": "GetTenant", "plan": "free"},
        )
        tid = create.json()["tenant_id"]
        resp = client.get(f"/api/v1/enterprise/tenants/{tid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == tid

    def test_get_missing_tenant_404(self, client):
        resp = client.get("/api/v1/enterprise/tenants/nonexistent", headers=H)
        assert resp.status_code == 404

    def test_delete_tenant(self, client):
        create = client.post(
            "/api/v1/enterprise/tenants",
            headers=H,
            json={"name": "DeleteMe", "plan": "free"},
        )
        tid = create.json()["tenant_id"]
        resp = client.delete(f"/api/v1/enterprise/tenants/{tid}", headers=H)
        assert resp.status_code == 200

    def test_delete_missing_tenant_404(self, client):
        resp = client.delete("/api/v1/enterprise/tenants/nonexistent", headers=H)
        assert resp.status_code == 404
