"""Jira REST v3 integration."""

from __future__ import annotations

import base64
import json
from typing import Any

try:
    import httpx

    _HTTPX = True
except ImportError:
    _HTTPX = False


class JiraIntegration:
    """Async Jira Cloud REST v3 client (Basic auth)."""

    def __init__(
        self, base_url: str = "", email: str = "", api_token: str = ""
    ) -> None:
        self._base = base_url.rstrip("/")
        creds = f"{email}:{api_token}"
        self._auth = "Basic " + base64.b64encode(creds.encode()).decode()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self._auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        if not _HTTPX:
            return {"issues": []}
        body = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields or ["summary", "status", "assignee"],
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base}/rest/api/3/issue/search",
                headers=self._headers(),
                content=json.dumps(body),
                timeout=15,
            )
        return r.json()

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        if not _HTTPX:
            return {}
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base}/rest/api/3/issue/{issue_key}",
                headers=self._headers(),
                timeout=15,
            )
        return r.json()

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str | None = None,
        priority: str = "Medium",
    ) -> dict[str, Any]:
        if not _HTTPX:
            return {}
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }
        if description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base}/rest/api/3/issue",
                headers=self._headers(),
                content=json.dumps({"fields": fields}),
                timeout=15,
            )
        return r.json()

    async def update_issue(self, issue_key: str, fields: dict[str, Any]) -> bool:
        if not _HTTPX:
            return False
        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{self._base}/rest/api/3/issue/{issue_key}",
                headers=self._headers(),
                content=json.dumps({"fields": fields}),
                timeout=15,
            )
        return r.status_code == 204

    async def add_comment(self, issue_key: str, text: str) -> dict[str, Any]:
        if not _HTTPX:
            return {}
        body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": text}]}
                ],
            }
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base}/rest/api/3/issue/{issue_key}/comment",
                headers=self._headers(),
                content=json.dumps(body),
                timeout=15,
            )
        return r.json()

    async def list_projects(self) -> list[dict[str, Any]]:
        if not _HTTPX:
            return []
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base}/rest/api/3/project",
                headers=self._headers(),
                timeout=15,
            )
        return r.json()

    def __repr__(self) -> str:
        return f"JiraIntegration(base={self._base!r})"
