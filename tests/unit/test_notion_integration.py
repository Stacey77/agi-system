"""Tests for Notion integration client and REST endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.key_store import KeyRole
from src.integrations.notion_client import NotionClient


def _api_key_mock(role: str = "admin"):
    m = MagicMock()
    m.role = KeyRole(role)
    m.key_id = "k1"
    m.name = "test"
    return m


# ---------------------------------------------------------------------------
# NotionClient unit tests (no HTTP)
# ---------------------------------------------------------------------------

class TestNotionClientUnit:
    def test_is_configured_with_key(self):
        client = NotionClient(api_key="secret-token")
        assert client.is_configured() is True

    def test_is_configured_without_key(self, monkeypatch):
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        client = NotionClient(api_key="")
        assert client.is_configured() is False

    def test_headers_contain_auth(self):
        client = NotionClient(api_key="ntn_test123")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer ntn_test123"
        assert headers["Notion-Version"] == "2022-06-28"

    @pytest.mark.asyncio
    async def test_get_page_calls_correct_path(self):
        client = NotionClient(api_key="ntn_test")
        mock_response = {"id": "page-abc", "object": "page"}
        with patch.object(client, "_get", new=AsyncMock(return_value=mock_response)) as mock_get:
            result = await client.get_page("page-abc")
            mock_get.assert_called_once_with("/pages/page-abc")
            assert result["id"] == "page-abc"

    @pytest.mark.asyncio
    async def test_query_database_passes_filter(self):
        client = NotionClient(api_key="ntn_test")
        mock_response = {"results": [], "has_more": False}
        with patch.object(client, "_post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await client.query_database("db-123", filter_obj={"property": "Status"})
            call_body = mock_post.call_args[0][1]
            assert call_body["filter"] == {"property": "Status"}
            assert call_body["page_size"] == 50

    @pytest.mark.asyncio
    async def test_list_database_rows_paginates(self):
        client = NotionClient(api_key="ntn_test")
        page1 = {"results": [{"id": "r1"}], "has_more": True, "next_cursor": "cursor1"}
        page2 = {"results": [{"id": "r2"}], "has_more": False, "next_cursor": None}
        with patch.object(client, "_post", new=AsyncMock(side_effect=[page1, page2])):
            rows = await client.list_database_rows("db-xyz")
            assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_create_page_includes_content_block(self):
        client = NotionClient(api_key="ntn_test")
        mock_response = {"id": "new-page"}
        with patch.object(client, "_post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await client.create_page("db-parent", "My Title", content="Hello world")
            body = mock_post.call_args[0][1]
            assert "children" in body
            assert body["children"][0]["type"] == "paragraph"

    @pytest.mark.asyncio
    async def test_search_with_filter_type(self):
        client = NotionClient(api_key="ntn_test")
        mock_response = {"results": []}
        with patch.object(client, "_post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await client.search("docs", filter_type="database")
            body = mock_post.call_args[0][1]
            assert body["filter"]["value"] == "database"

    @pytest.mark.asyncio
    async def test_archive_page_sends_archived_true(self):
        client = NotionClient(api_key="ntn_test")
        with patch.object(client, "_patch", new=AsyncMock(return_value={})) as mock_patch:
            await client.archive_page("page-999")
            mock_patch.assert_called_once_with("/pages/page-999", {"archived": True})


# ---------------------------------------------------------------------------
# Notion API endpoints
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def notion_client_app():
    from src.api.main import create_app
    app = create_app()
    mock_notion = MagicMock(spec=NotionClient)
    mock_notion.is_configured.return_value = True
    with TestClient(app, raise_server_exceptions=True) as c:
        app.state.notion_client = mock_notion
        app.state.key_store = MagicMock()
        app.state.key_store.validate_key.return_value = _api_key_mock()
        app.state.jwt_manager = MagicMock()
        app.state.jwt_manager.verify_token.return_value = None
        yield c, mock_notion


H = {"X-API-Key": "sk-test"}


class TestNotionStatusEndpoint:
    def test_status_configured(self, monkeypatch, notion_client_app):
        monkeypatch.setenv("NOTION_API_KEY", "ntn_test")
        c, _ = notion_client_app
        resp = c.get("/api/v1/notion/status", headers=H)
        assert resp.status_code == 200
        assert resp.json()["configured"] is True

    def test_status_not_configured(self, monkeypatch, notion_client_app):
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        c, _ = notion_client_app
        resp = c.get("/api/v1/notion/status", headers=H)
        assert resp.status_code == 200
        assert resp.json()["configured"] is False


class TestNotionPageEndpoints:
    def test_get_page(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.get_page = AsyncMock(return_value={"id": "page-1", "object": "page"})
        resp = c.get("/api/v1/notion/pages/page-1", headers=H)
        assert resp.status_code == 200
        assert resp.json()["id"] == "page-1"

    def test_get_page_content(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.get_page_content = AsyncMock(
            return_value=[{"type": "paragraph", "id": "block-1"}]
        )
        resp = c.get("/api/v1/notion/pages/page-1/content", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["blocks"]) == 1

    def test_create_page(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.create_page = AsyncMock(return_value={"id": "new-page", "object": "page"})
        resp = c.post("/api/v1/notion/pages", headers=H, json={
            "parent_id": "db-parent",
            "title": "New Doc",
            "content": "hello",
        })
        assert resp.status_code == 200
        assert resp.json()["id"] == "new-page"

    def test_update_page(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.update_page = AsyncMock(return_value={"id": "page-1"})
        resp = c.patch("/api/v1/notion/pages/page-1", headers=H,
                       json={"properties": {"Status": {"select": {"name": "Done"}}}})
        assert resp.status_code == 200

    def test_archive_page(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.archive_page = AsyncMock(return_value={"id": "page-1", "archived": True})
        resp = c.delete("/api/v1/notion/pages/page-1", headers=H)
        assert resp.status_code == 200

    def test_append_blocks(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.append_blocks = AsyncMock(return_value={"results": []})
        resp = c.post("/api/v1/notion/pages/page-1/blocks", headers=H, json={
            "blocks": [{"type": "paragraph", "paragraph": {"rich_text": []}}]
        })
        assert resp.status_code == 200


class TestNotionDatabaseEndpoints:
    def test_get_database(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.get_database = AsyncMock(return_value={"id": "db-1", "object": "database"})
        resp = c.get("/api/v1/notion/databases/db-1", headers=H)
        assert resp.status_code == 200
        assert resp.json()["object"] == "database"

    def test_query_database(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.query_database = AsyncMock(
            return_value={"results": [{"id": "row-1"}], "has_more": False}
        )
        resp = c.post("/api/v1/notion/databases/db-1/query", headers=H,
                      json={"page_size": 10})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1

    def test_list_database_rows(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.list_database_rows = AsyncMock(
            return_value=[{"id": "r1"}, {"id": "r2"}]
        )
        resp = c.get("/api/v1/notion/databases/db-1/rows", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["rows"]) == 2


class TestNotionSearchEndpoint:
    def test_search(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.search = AsyncMock(
            return_value={"results": [{"id": "p1", "object": "page"}]}
        )
        resp = c.post("/api/v1/notion/search", headers=H,
                      json={"query": "AGI", "filter_type": "page"})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1

    def test_search_database_filter(self, notion_client_app):
        c, mock_notion = notion_client_app
        mock_notion.search = AsyncMock(return_value={"results": []})
        resp = c.post("/api/v1/notion/search", headers=H,
                      json={"query": "tasks", "filter_type": "database"})
        assert resp.status_code == 200
        mock_notion.search.assert_called_once_with(
            query="tasks", filter_type="database", page_size=20
        )
