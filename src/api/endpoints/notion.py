"""Notion integration endpoints — pages, databases, search, and CMS helpers."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.integrations.notion_client import NotionClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notion", tags=["notion"])


# ---------------------------------------------------------------------------
# Shared client helper
# ---------------------------------------------------------------------------


def _client(request: Request) -> NotionClient:
    client = getattr(request.app.state, "notion_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="Notion client not initialised")
    if not client.is_configured():
        raise HTTPException(
            status_code=503,
            detail="NOTION_API_KEY is not set — Notion integration unavailable",
        )
    return client


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class CreatePageRequest(BaseModel):
    parent_id: str
    title: str
    content: str = ""
    parent_type: str = "database"


class UpdatePageRequest(BaseModel):
    properties: Dict[str, Any]


class AppendBlocksRequest(BaseModel):
    blocks: List[Dict[str, Any]]


class QueryDatabaseRequest(BaseModel):
    filter: Optional[Dict[str, Any]] = None
    sorts: Optional[List[Dict[str, Any]]] = None
    page_size: int = 50


class NotionSearchRequest(BaseModel):
    query: str
    filter_type: Optional[str] = None
    page_size: int = 20


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/status")
async def notion_status(request: Request) -> Dict[str, Any]:
    """Check whether the Notion integration is configured."""
    api_key_set = bool(os.getenv("NOTION_API_KEY"))
    return {
        "configured": api_key_set,
        "message": "Notion integration active" if api_key_set else "Set NOTION_API_KEY to enable",
    }


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@router.get("/pages/{page_id}")
async def get_page(page_id: str, request: Request) -> Dict[str, Any]:
    """Fetch a Notion page by ID."""
    try:
        return await _client(request).get_page(page_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/pages/{page_id}/content")
async def get_page_content(page_id: str, request: Request) -> Dict[str, Any]:
    """Return all block children of a Notion page."""
    try:
        blocks = await _client(request).get_page_content(page_id)
        return {"page_id": page_id, "blocks": blocks, "count": len(blocks)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/pages")
async def create_page(body: CreatePageRequest, request: Request) -> Dict[str, Any]:
    """Create a new Notion page under a database or page parent."""
    try:
        return await _client(request).create_page(
            parent_id=body.parent_id,
            title=body.title,
            content=body.content,
            parent_type=body.parent_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.patch("/pages/{page_id}")
async def update_page(
    page_id: str, body: UpdatePageRequest, request: Request
) -> Dict[str, Any]:
    """Update properties on an existing Notion page."""
    try:
        return await _client(request).update_page(page_id, body.properties)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/pages/{page_id}")
async def archive_page(page_id: str, request: Request) -> Dict[str, Any]:
    """Archive (soft-delete) a Notion page."""
    try:
        return await _client(request).archive_page(page_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/pages/{page_id}/blocks")
async def append_blocks(
    page_id: str, body: AppendBlocksRequest, request: Request
) -> Dict[str, Any]:
    """Append block children to a Notion page."""
    try:
        return await _client(request).append_blocks(page_id, body.blocks)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Databases
# ---------------------------------------------------------------------------


@router.get("/databases/{database_id}")
async def get_database(database_id: str, request: Request) -> Dict[str, Any]:
    """Fetch a Notion database schema."""
    try:
        return await _client(request).get_database(database_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/databases/{database_id}/query")
async def query_database(
    database_id: str, body: QueryDatabaseRequest, request: Request
) -> Dict[str, Any]:
    """Query a Notion database with optional filter and sort."""
    try:
        return await _client(request).query_database(
            database_id=database_id,
            filter_obj=body.filter,
            sorts=body.sorts,
            page_size=body.page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/databases/{database_id}/rows")
async def list_database_rows(
    database_id: str, request: Request
) -> Dict[str, Any]:
    """Return all rows from a Notion database (handles pagination automatically)."""
    try:
        rows = await _client(request).list_database_rows(database_id)
        return {"database_id": database_id, "rows": rows, "count": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@router.post("/search")
async def search_notion(body: NotionSearchRequest, request: Request) -> Dict[str, Any]:
    """Search across all Notion pages and databases the integration can access."""
    try:
        return await _client(request).search(
            query=body.query,
            filter_type=body.filter_type,
            page_size=body.page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
