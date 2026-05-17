"""Writing agent — content generation with outline→draft→edit pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from src.agents.base_agent import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Represents a generated document."""

    title: str
    content: str = ""
    outline: List[str] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    word_count: int = 0
    tone: str = "professional"
    citations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WritingAgent(BaseAgent):
    """Generates high-quality content through a structured pipeline."""

    _OUTLINE_PROMPT = (
        "You are a skilled writer. Given a topic, format, and target audience, generate a "
        "document outline as a JSON array of section heading strings. "
        "Respond ONLY with a JSON array — no markdown, no explanation."
    )
    _SECTION_PROMPT = (
        "You are a skilled writer. Write the content for the section '{heading}' of a "
        "{format} about '{topic}'. Tone: {tone}. Audience: {audience}. "
        "Write 2-4 substantial paragraphs. No headings, just prose."
    )

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
        llm: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent, llm)

    async def stream_task(self, task: Dict[str, Any]) -> AsyncIterator[str]:
        """Stream document content token-by-token when an LLM is available."""
        if self.llm is None:
            import json
            result = await self.process_task(task)
            yield json.dumps(result)
            return

        topic = task.get("topic", task.get("task", ""))
        requirements = task.get("requirements", {})
        tone = requirements.get("tone", "professional")
        audience = requirements.get("audience", "general")
        doc_format = requirements.get("format", "article")

        prompt = (
            f"Write a {tone} {doc_format} about '{topic}' for a {audience} audience. "
            "Use clear markdown headings for each section."
        )
        async for chunk in self._stream_llm(prompt):
            yield chunk

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a writing task."""
        topic = task.get("topic", task.get("task", ""))
        requirements = task.get("requirements", {})
        logger.info("WritingAgent creating document on topic: %s", topic)

        doc = await self.create_document(topic, requirements)

        result: Dict[str, Any] = {
            "status": "completed",
            "title": doc.title,
            "content": doc.content,
            "outline": doc.outline,
            "word_count": doc.word_count,
            "tone": doc.tone,
            "citations": doc.citations,
        }
        self._record_task(task, result)
        return result

    async def create_document(
        self, topic: str, requirements: Dict[str, Any]
    ) -> Document:
        """Generate a document through the outline→draft→edit pipeline."""
        tone = requirements.get("tone", "professional")
        audience = requirements.get("audience", "general")
        doc_format = requirements.get("format", "article")

        outline = (
            await self._llm_create_outline(topic, doc_format, audience)
            or self._create_outline(topic, doc_format)
        )
        sections = await self._llm_draft_sections(outline, topic, tone, audience, doc_format)
        content = self._assemble_content(sections)
        content = self._edit_content(content, requirements)

        return Document(
            title=f"{topic} — {doc_format.title()}",
            content=content,
            outline=outline,
            sections=sections,
            word_count=len(content.split()),
            tone=tone,
            citations=requirements.get("citations", []),
        )

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    async def _llm_create_outline(
        self, topic: str, doc_format: str, audience: str
    ) -> Optional[List[str]]:
        """Ask the LLM to produce an outline; return None on failure."""
        import json

        user_prompt = f"Topic: {topic}\nFormat: {doc_format}\nAudience: {audience}"
        raw = await self._invoke_llm(self._OUTLINE_PROMPT, user_prompt)
        if not raw:
            return None
        try:
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```")
            outline: List[str] = json.loads(raw)
            if isinstance(outline, list) and outline:
                return outline
        except (json.JSONDecodeError, ValueError):
            logger.warning("LLM outline response was not JSON; using default outline")
        return None

    async def _llm_draft_sections(
        self,
        outline: List[str],
        topic: str,
        tone: str,
        audience: str,
        doc_format: str,
    ) -> List[Dict[str, Any]]:
        """Draft each section using the LLM if available, else use placeholder text."""
        sections: List[Dict[str, Any]] = []
        for heading in outline:
            if self.llm is not None:
                prompt = self._SECTION_PROMPT.format(
                    heading=heading,
                    format=doc_format,
                    topic=topic,
                    tone=tone,
                    audience=audience,
                )
                content = await self._invoke_llm("", prompt) or (
                    f"[{tone.upper()} | {audience}] Content for '{heading}' related to {topic}."
                )
            else:
                content = f"[{tone.upper()} | {audience}] Content for '{heading}' related to {topic}."
            sections.append({"heading": heading, "content": content})
        return sections

    def _create_outline(self, topic: str, doc_format: str) -> List[str]:
        if doc_format == "report":
            return [
                "Executive Summary",
                "Introduction",
                "Background",
                "Analysis",
                "Findings",
                "Recommendations",
                "Conclusion",
            ]
        return [
            "Introduction",
            f"Overview of {topic}",
            "Key Concepts",
            "Practical Applications",
            "Conclusion",
        ]

    def _assemble_content(self, sections: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for section in sections:
            parts.append(f"## {section['heading']}\n\n{section['content']}")
        return "\n\n".join(parts)

    def _edit_content(self, content: str, requirements: Dict[str, Any]) -> str:
        max_words = requirements.get("max_words")
        if max_words:
            words = content.split()
            if len(words) > max_words:
                content = " ".join(words[:max_words]) + "..."
        return content
