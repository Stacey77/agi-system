"""Web search tool — integrates with search APIs (Tavily/Serper/Brave)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.tools.base_tool import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Performs web searches and returns structured results."""

    def __init__(self, api_key: Optional[str] = None, provider: str = "mock") -> None:
        self._api_key = api_key
        self._provider = provider

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="web_search",
            description="Search the web and return relevant results",
            parameters={
                "required": ["query"],
                "optional": ["max_results"],
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {
                        "type": "integer",
                        "default": 5,
                        "description": "Maximum results to return",
                    },
                },
            },
            return_type="List[Dict]",
            category="information_retrieval",
        )

    def execute(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """Execute a web search and return a list of result dicts."""
        if not self.validate_parameters(**kwargs):
            return []

        query = kwargs["query"]
        max_results = int(kwargs.get("max_results", 5))

        if self._api_key and self._provider != "mock":
            return self._live_search(query, max_results)
        return self._mock_search(query, max_results)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _live_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform a live search using the configured provider."""
        try:
            if self._provider == "tavily":
                return self._search_tavily(query, max_results)
            if self._provider == "serper":
                return self._search_serper(query, max_results)
            return self._mock_search(query, max_results)
        except Exception as exc:  # noqa: BLE001
            logger.error("Live search failed: %s — falling back to mock", exc)
            return self._mock_search(query, max_results)

    def _search_tavily(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Tavily search integration (requires tavily-python package)."""
        try:
            from tavily import TavilyClient  # type: ignore[import]

            client = TavilyClient(api_key=self._api_key)
            resp = client.search(query=query, max_results=max_results)
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                }
                for r in resp.get("results", [])
            ]
        except ImportError:
            logger.warning("tavily-python not installed; falling back to mock")
            return self._mock_search(query, max_results)

    def _search_serper(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Serper.dev search integration."""
        try:
            import httpx

            resp = httpx.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": self._api_key or "", "Content-Type": "application/json"},
                json={"q": query, "num": max_results},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "snippet": r.get("snippet", ""),
                }
                for r in data.get("organic", [])[:max_results]
            ]
        except Exception as exc:  # noqa: BLE001
            logger.error("Serper search failed: %s", exc)
            return self._mock_search(query, max_results)

    def _mock_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        return [
            {
                "title": f"Result {i + 1} for '{query}'",
                "url": f"https://example.com/result-{i + 1}",
                "snippet": f"Mock snippet {i + 1} about {query}.",
            }
            for i in range(min(max_results, 3))
        ]
