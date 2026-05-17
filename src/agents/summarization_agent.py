"""Summarization agent — condenses text, documents, and research into digestible summaries."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base_agent import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class SummaryResult:
    """Output of the summarization agent."""

    original_length: int
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    style: str = "concise"
    compression_ratio: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SummarizationAgent(BaseAgent):
    """Produces concise summaries in multiple styles using an LLM or extractive fallback."""

    _SYSTEM_PROMPT = (
        "You are an expert summarizer. Given text and a style, produce a summary. "
        "Return a JSON object with keys: "
        "summary (string), key_points (list of up to 5 bullet strings). "
        "Styles: 'concise' (1-2 sentences), 'detailed' (full paragraph), "
        "'bullet' (bullet list), 'executive' (executive-briefing prose). "
        "Respond ONLY with valid JSON."
    )

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
        llm: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent, llm)

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a summarization task.

        Expected task keys:
        - ``text`` (str): the content to summarise
        - ``style`` (str, optional): concise | detailed | bullet | executive
        - ``max_length`` (int, optional): soft word-count cap on the summary
        """
        text = task.get("text", task.get("task", ""))
        style = task.get("style", "concise")
        max_length = task.get("max_length")
        logger.info("SummarizationAgent style=%s text_length=%d", style, len(text))

        result_obj = await self.summarize(text, style=style, max_length=max_length)

        result: Dict[str, Any] = {
            "status": "completed",
            "summary": result_obj.summary,
            "key_points": result_obj.key_points,
            "style": result_obj.style,
            "original_length": result_obj.original_length,
            "compression_ratio": result_obj.compression_ratio,
        }
        self._record_task(task, result)
        return result

    async def summarize(
        self,
        text: str,
        style: str = "concise",
        max_length: Optional[int] = None,
    ) -> SummaryResult:
        """Summarize *text* in the requested *style*."""
        original_length = len(text.split())
        import json

        user_prompt = f"Style: {style}\nText:\n{text}"
        if max_length:
            user_prompt += f"\n\nMax summary length: {max_length} words"

        raw = await self._invoke_llm(self._SYSTEM_PROMPT, user_prompt)
        if raw:
            try:
                cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```")
                parsed: Dict[str, Any] = json.loads(cleaned)
                summary = parsed.get("summary", "")
                key_points = parsed.get("key_points", [])
                summary_length = len(summary.split())
                compression = (
                    round(1 - summary_length / original_length, 2) if original_length > 0 else 0.0
                )
                return SummaryResult(
                    original_length=original_length,
                    summary=summary,
                    key_points=key_points,
                    style=style,
                    compression_ratio=compression,
                )
            except (json.JSONDecodeError, ValueError):
                summary = raw.strip()
                compression = (
                    round(1 - len(summary.split()) / original_length, 2)
                    if original_length > 0
                    else 0.0
                )
                return SummaryResult(
                    original_length=original_length,
                    summary=summary,
                    style=style,
                    compression_ratio=compression,
                )

        return self._extractive_summary(text, style, original_length)

    def _extractive_summary(
        self, text: str, style: str, original_length: int
    ) -> SummaryResult:
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
        n = 1 if style == "concise" else min(5, len(sentences))
        summary = ". ".join(sentences[:n]) + ("." if sentences[:n] else "")
        key_points = [f"* {s}." for s in sentences[:5]]
        summary_length = len(summary.split())
        compression = (
            round(1 - summary_length / original_length, 2) if original_length > 0 else 0.0
        )
        return SummaryResult(
            original_length=original_length,
            summary=summary,
            key_points=key_points,
            style=style,
            compression_ratio=compression,
        )
