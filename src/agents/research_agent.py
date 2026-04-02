"""Research agent — multi-source information gathering."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base_agent import AgentConfig, BaseAgent
from src.integrations.langchain_integration import create_langchain_chain

logger = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    """Aggregated research output."""

    query: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    quality_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResearchAgent(BaseAgent):
    """Gathers information from multiple sources and assesses quality."""

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent)
        self._chain = create_langchain_chain(
            role="research", temperature=config.temperature
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a research task."""
        query = task.get("query", task.get("task", ""))
        logger.info("ResearchAgent conducting research on: %s", query)

        research = await self.conduct_research(query)

        result: Dict[str, Any] = {
            "status": "completed",
            "query": research.query,
            "sources": research.sources,
            "summary": research.summary,
            "quality_score": research.quality_score,
        }
        self._record_task(task, result)
        return result

    async def conduct_research(self, query: str) -> ResearchResult:
        """Conduct parallel research across multiple tools, then synthesise with LangChain."""
        search_tools = [t for t in self.config.tools if "search" in t.lower()]
        if not search_tools:
            search_tools = ["web_search"]

        results = await asyncio.gather(
            *[self._search_source(query, tool) for tool in search_tools],
            return_exceptions=True,
        )

        sources: List[Dict[str, Any]] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Search failed: %s", r)
            elif isinstance(r, list):
                sources.extend(r)

        quality = self._assess_quality(sources)
        summary = self._synthesise_summary(query, sources)

        return ResearchResult(
            query=query,
            sources=sources,
            summary=summary,
            quality_score=quality,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _search_source(
        self, query: str, tool_name: str
    ) -> List[Dict[str, Any]]:
        tool = self._get_tool(tool_name)
        if tool is None:
            return [
                {
                    "source": tool_name,
                    "title": f"Mock result for '{query}'",
                    "url": "https://example.com",
                    "snippet": f"Information about {query}",
                }
            ]
        raw = await asyncio.to_thread(tool.execute, query=query)
        return raw if isinstance(raw, list) else [raw]

    def _assess_quality(self, sources: List[Dict[str, Any]]) -> float:
        if not sources:
            return 0.0
        return min(1.0, len(sources) / 5.0)

    def _synthesise_summary(
        self, query: str, sources: List[Dict[str, Any]]
    ) -> str:
        """Build a summary, using the LangChain chain when available."""
        if not sources:
            raw_context = "No sources found."
        else:
            snippets = [s.get("snippet", "") for s in sources[:5] if s.get("snippet")]
            raw_context = " ".join(snippets) if snippets else "Sources gathered but no snippets available."

        # Attempt LangChain synthesis
        try:
            return self._chain.run(query=query, context=raw_context)
        except Exception as exc:  # noqa: BLE001
            logger.debug("LangChain synthesis skipped: %s", exc)
            return f"Research on '{query}': {raw_context}"
