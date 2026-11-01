"""GitHub REST API v3 integration."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False

_BASE = "https://api.github.com"


class GitHubIntegration:
    """Async GitHub REST client (Bearer token auth)."""

    def __init__(self, token: str = "") -> None:
        self._token = token

    def _headers(self) -> Dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def list_repos(self, owner: str, per_page: int = 30) -> List[Dict[str, Any]]:
        if not _HTTPX:
            return []
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{_BASE}/users/{owner}/repos",
                headers=self._headers(),
                params={"per_page": per_page},
                timeout=15,
            )
        return r.json()

    async def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        if not _HTTPX:
            return {}
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{_BASE}/repos/{owner}/{repo}", headers=self._headers(), timeout=15)
        return r.json()

    async def list_issues(
        self, owner: str, repo: str, state: str = "open", per_page: int = 30
    ) -> List[Dict[str, Any]]:
        if not _HTTPX:
            return []
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{_BASE}/repos/{owner}/{repo}/issues",
                headers=self._headers(),
                params={"state": state, "per_page": per_page},
                timeout=15,
            )
        return r.json()

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not _HTTPX:
            return {}
        payload: Dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{_BASE}/repos/{owner}/{repo}/issues",
                headers=self._headers(),
                content=json.dumps(payload),
                timeout=15,
            )
        return r.json()

    async def list_pull_requests(
        self, owner: str, repo: str, state: str = "open", per_page: int = 30
    ) -> List[Dict[str, Any]]:
        if not _HTTPX:
            return []
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{_BASE}/repos/{owner}/{repo}/pulls",
                headers=self._headers(),
                params={"state": state, "per_page": per_page},
                timeout=15,
            )
        return r.json()

    async def create_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> Dict[str, Any]:
        if not _HTTPX:
            return {}
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                headers=self._headers(),
                content=json.dumps({"body": body}),
                timeout=15,
            )
        return r.json()

    async def get_workflow_runs(
        self, owner: str, repo: str, per_page: int = 10
    ) -> Dict[str, Any]:
        if not _HTTPX:
            return {}
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{_BASE}/repos/{owner}/{repo}/actions/runs",
                headers=self._headers(),
                params={"per_page": per_page},
                timeout=15,
            )
        return r.json()

    def __repr__(self) -> str:
        return f"GitHubIntegration(token={'***' if self._token else 'none'})"
