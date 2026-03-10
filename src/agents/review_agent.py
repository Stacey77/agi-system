"""Review agent — quality assurance, fact-checking, and self-correction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base_agent import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Outcome of the review process."""

    is_approved: bool
    score: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    corrected_content: Optional[Any] = None
    reflection_notes: List[str] = field(default_factory=list)


class ReviewAgent(BaseAgent):
    """Validates and quality-assures output from other agents."""

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent)

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a review task."""
        content = task.get("content")
        criteria = task.get("criteria", {})
        logger.info("ReviewAgent reviewing content with criteria: %s", list(criteria.keys()))

        review = await self.review_output(content, criteria)

        result: Dict[str, Any] = {
            "status": "completed",
            "is_approved": review.is_approved,
            "score": review.score,
            "issues": review.issues,
            "suggestions": review.suggestions,
            "reflection_notes": review.reflection_notes,
        }
        if review.corrected_content is not None:
            result["corrected_content"] = review.corrected_content
        self._record_task(task, result)
        return result

    async def review_output(
        self, content: Any, criteria: Dict[str, Any]
    ) -> ReviewResult:
        """Review content against the provided criteria."""
        issues: List[str] = []
        suggestions: List[str] = []
        notes: List[str] = []

        # Completeness check
        if content is None or content == "":
            issues.append("Content is empty")
        else:
            notes.append("Content is present — completeness check passed")

        # Length check
        min_length = criteria.get("min_length", 0)
        if isinstance(content, str) and len(content) < min_length:
            issues.append(f"Content too short: {len(content)} < {min_length}")
            suggestions.append("Expand the content to meet minimum length requirements")

        # Required keywords check
        required_keywords = criteria.get("required_keywords", [])
        if isinstance(content, str):
            for kw in required_keywords:
                if kw.lower() not in content.lower():
                    issues.append(f"Missing required keyword: '{kw}'")

        # Reflection loop — attempt self-correction
        corrected: Optional[Any] = None
        if issues and isinstance(content, str):
            corrected = self._self_correct(content, issues)
            notes.append("Self-correction applied based on identified issues")

        score = max(0.0, 1.0 - (len(issues) * 0.2))
        is_approved = len(issues) == 0 and score >= criteria.get("min_score", 0.6)

        return ReviewResult(
            is_approved=is_approved,
            score=score,
            issues=issues,
            suggestions=suggestions,
            corrected_content=corrected,
            reflection_notes=notes,
        )

    # ------------------------------------------------------------------
    # Self-correction
    # ------------------------------------------------------------------

    def _self_correct(self, content: str, issues: List[str]) -> str:
        corrections = [f"[Correction: {issue}]" for issue in issues]
        return content + "\n\n" + "\n".join(corrections)
