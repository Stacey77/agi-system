"""Notion API client — read/write pages and databases via the Notion REST API."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_NOTION_VERSION = "2022-06-28"
_BASE_URL = "https://api.notion.com/v1"


class NotionClient:
    """Thin async wrapper around the Notion REST API."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("NOTION_API_KEY", "")
        if not self._api_key:
            logger.warning("NOTION_API_KEY not set — Notion calls will fail")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BASE_URL}{path}",
                headers=self._headers(),
                params=params or {},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, body: Dict) -> Any:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE_URL}{path}",
                headers=self._headers(),
                json=body,
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def _patch(self, path: str, body: Dict) -> Any:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{_BASE_URL}{path}",
                headers=self._headers(),
                json=body,
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """Fetch a single Notion page by ID."""
        return await self._get(f"/pages/{page_id}")

    async def create_page(
        self,
        parent_id: str,
        title: str,
        content: str = "",
        parent_type: str = "database",
    ) -> Dict[str, Any]:
        """Create a new page under a database or page parent."""
        parent_key = "database_id" if parent_type == "database" else "page_id"
        body: Dict[str, Any] = {
            "parent": {parent_key: parent_id},
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            },
        }
        if content:
            body["children"] = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    },
                }
            ]
        return await self._post("/pages", body)

    async def update_page(
        self, page_id: str, properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update properties on an existing page."""
        return await self._patch(f"/pages/{page_id}", {"properties": properties})

    async def archive_page(self, page_id: str) -> Dict[str, Any]:
        """Archive (soft-delete) a page."""
        return await self._patch(f"/pages/{page_id}", {"archived": True})

    # ------------------------------------------------------------------
    # Blocks
    # ------------------------------------------------------------------

    async def get_page_content(self, page_id: str) -> List[Dict[str, Any]]:
        """Return the block children of a page."""
        data = await self._get(f"/blocks/{page_id}/children")
        return data.get("results", [])

    async def append_blocks(
        self, page_id: str, blocks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Append block children to a page."""
        return await self._post(f"/blocks/{page_id}/children", {"children": blocks})

    # ------------------------------------------------------------------
    # Databases
    # ------------------------------------------------------------------

    async def query_database(
        self,
        database_id: str,
        filter_obj: Optional[Dict] = None,
        sorts: Optional[List[Dict]] = None,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """Query a Notion database with optional filter and sort."""
        body: Dict[str, Any] = {"page_size": min(page_size, 100)}
        if filter_obj:
            body["filter"] = filter_obj
        if sorts:
            body["sorts"] = sorts
        return await self._post(f"/databases/{database_id}/query", body)

    async def get_database(self, database_id: str) -> Dict[str, Any]:
        """Fetch a database schema."""
        return await self._get(f"/databases/{database_id}")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        filter_type: Optional[str] = None,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Search across all pages and databases the integration can access."""
        body: Dict[str, Any] = {"query": query, "page_size": min(page_size, 100)}
        if filter_type in ("page", "database"):
            body["filter"] = {"value": filter_type, "property": "object"}
        return await self._post("/search", body)

    # ------------------------------------------------------------------
    # CMS helpers — used by agents
    # ------------------------------------------------------------------

    async def list_database_rows(self, database_id: str) -> List[Dict[str, Any]]:
        """Return all rows from a Notion database (handles pagination)."""
        rows: List[Dict[str, Any]] = []
        has_more = True
        cursor: Optional[str] = None
        while has_more:
            body: Dict[str, Any] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            data = await self._post(f"/databases/{database_id}/query", body)
            rows.extend(data.get("results", []))
            has_more = data.get("has_more", False)
            cursor = data.get("next_cursor")
        return rows

    def is_configured(self) -> bool:
        return bool(self._api_key)
