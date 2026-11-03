"""Unit tests for the integrations hub API endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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
# Integration listing
# ---------------------------------------------------------------------------

class TestIntegrationsList:
    def test_integrations_status(self, client):
        resp = client.get("/api/v1/integrations/status", headers=H)
        assert resp.status_code == 200

    def test_jira_projects_unconfigured(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            app.state.key_store = MagicMock()
            app.state.key_store.validate_key.return_value = _api_key_mock()
            app.state.jwt_manager = MagicMock()
            app.state.jwt_manager.verify_token.return_value = None
            app.state.jira_integration = None
            resp = c.get("/api/v1/integrations/jira/projects", headers=H)
            assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Unconfigured integrations return 503
# ---------------------------------------------------------------------------

class TestUnconfiguredIntegrations:
    """When integration clients are not set on app.state they return 503."""

    @pytest.fixture()
    def bare_client(self):
        """App with no integration state set."""
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            app.state.key_store = MagicMock()
            app.state.key_store.validate_key.return_value = _api_key_mock()
            app.state.jwt_manager = MagicMock()
            app.state.jwt_manager.verify_token.return_value = None
            # Explicitly remove integration state so _get() raises 503
            app.state.slack_integration = None
            app.state.jira_integration = None
            app.state.github_integration = None
            app.state.teams_integration = None
            yield c

    def test_slack_message_unconfigured_503(self, bare_client):
        resp = bare_client.post("/api/v1/integrations/slack/message", headers=H,
                                json={"channel": "#general", "text": "hello"})
        assert resp.status_code == 503

    def test_jira_create_issue_unconfigured_503(self, bare_client):
        resp = bare_client.post("/api/v1/integrations/jira/issues", headers=H,
                                json={"project_key": "TEST", "summary": "Test issue",
                                      "description": "desc", "issue_type": "Task"})
        assert resp.status_code == 503

    def test_github_create_issue_unconfigured_503(self, bare_client):
        resp = bare_client.post("/api/v1/integrations/github/acme/myrepo/issues", headers=H,
                                json={"title": "Bug", "body": "Something broke"})
        assert resp.status_code == 503

    def test_teams_message_unconfigured_503(self, bare_client):
        resp = bare_client.post("/api/v1/integrations/teams/message", headers=H,
                                json={"title": "Alert", "text": "Something happened"})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Mocked integration sends (configured path)
# ---------------------------------------------------------------------------

class TestSlackIntegration:
    @pytest.fixture()
    def patched_client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        app = create_app()

        mock_slack = MagicMock()
        mock_slack.post_message = AsyncMock(return_value={"ok": True, "ts": "12345.67890"})

        with TestClient(app, raise_server_exceptions=True) as c:
            app.state.key_store = MagicMock()
            app.state.key_store.validate_key.return_value = _api_key_mock()
            app.state.jwt_manager = MagicMock()
            app.state.jwt_manager.verify_token.return_value = None
            app.state.slack_integration = mock_slack
            yield c

    def test_slack_send_success(self, patched_client):
        resp = patched_client.post("/api/v1/integrations/slack/message", headers=H,
                                   json={"channel": "#general", "text": "hello"})
        assert resp.status_code == 200


class TestJiraIntegration:
    @pytest.fixture()
    def patched_client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        app = create_app()

        mock_jira = MagicMock()
        mock_jira.create_issue = AsyncMock(return_value={
            "id": "10001", "key": "TEST-1", "self": "https://jira.example.com/rest/api/3/issue/10001"
        })

        with TestClient(app, raise_server_exceptions=True) as c:
            app.state.key_store = MagicMock()
            app.state.key_store.validate_key.return_value = _api_key_mock()
            app.state.jwt_manager = MagicMock()
            app.state.jwt_manager.verify_token.return_value = None
            app.state.jira_integration = mock_jira
            yield c

    def test_jira_create_issue_success(self, patched_client):
        resp = patched_client.post("/api/v1/integrations/jira/issues", headers=H,
                                   json={"project_key": "TEST", "summary": "Test issue",
                                         "description": "desc", "issue_type": "Task"})
        assert resp.status_code == 200


class TestGitHubIntegration:
    @pytest.fixture()
    def patched_client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        app = create_app()

        mock_gh = MagicMock()
        mock_gh.create_issue = AsyncMock(return_value={
            "number": 42, "title": "Bug", "html_url": "https://github.com/acme/repo/issues/42"
        })

        with TestClient(app, raise_server_exceptions=True) as c:
            app.state.key_store = MagicMock()
            app.state.key_store.validate_key.return_value = _api_key_mock()
            app.state.jwt_manager = MagicMock()
            app.state.jwt_manager.verify_token.return_value = None
            app.state.github_integration = mock_gh
            yield c

    def test_github_create_issue_success(self, patched_client):
        resp = patched_client.post("/api/v1/integrations/github/acme/myrepo/issues", headers=H,
                                   json={"title": "Bug", "body": "Something broke"})
        assert resp.status_code == 200


class TestTeamsIntegration:
    @pytest.fixture()
    def patched_client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        app = create_app()

        mock_teams = MagicMock()
        mock_teams.send_message = AsyncMock(return_value={"status": "sent"})

        with TestClient(app, raise_server_exceptions=True) as c:
            app.state.key_store = MagicMock()
            app.state.key_store.validate_key.return_value = _api_key_mock()
            app.state.jwt_manager = MagicMock()
            app.state.jwt_manager.verify_token.return_value = None
            app.state.teams_integration = mock_teams
            yield c

    def test_teams_send_success(self, patched_client):
        resp = patched_client.post("/api/v1/integrations/teams/message", headers=H,
                                   json={"title": "Alert", "text": "Something happened"})
        assert resp.status_code == 200
