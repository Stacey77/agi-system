"""Writing agent — content generation with outline→draft→edit pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent)

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

        outline = self._create_outline(topic, doc_format)
        sections = self._draft_sections(outline, topic, tone, audience)
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

    def _draft_sections(
        self,
        outline: List[str],
        topic: str,
        tone: str,
        audience: str,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "heading": heading,
                "content": (
                    f"[{tone.upper()} | {audience}] "
                    f"Content for '{heading}' related to {topic}."
                ),
            }
            for heading in outline
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
