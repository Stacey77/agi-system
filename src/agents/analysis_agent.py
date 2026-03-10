"""Analysis agent — data processing and insight extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base_agent import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Output of the analysis agent."""

    analysis_type: str
    insights: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0


class AnalysisAgent(BaseAgent):
    """Processes data and extracts insights."""

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent)

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process an analysis task."""
        data = task.get("data", {})
        analysis_type = task.get("analysis_type", "general")
        logger.info("AnalysisAgent running analysis type: %s", analysis_type)

        analysis = await self.analyze_data(data, analysis_type)

        result: Dict[str, Any] = {
            "status": "completed",
            "analysis_type": analysis.analysis_type,
            "insights": analysis.insights,
            "patterns": analysis.patterns,
            "statistics": analysis.statistics,
            "recommendations": analysis.recommendations,
            "confidence": analysis.confidence,
        }
        self._record_task(task, result)
        return result

    async def analyze_data(
        self, data: Dict[str, Any], analysis_type: str
    ) -> AnalysisResult:
        """Perform the requested analysis on the provided data."""
        handler = {
            "statistical": self._statistical_analysis,
            "pattern": self._pattern_analysis,
            "sentiment": self._sentiment_analysis,
        }.get(analysis_type, self._general_analysis)

        return handler(data)

    # ------------------------------------------------------------------
    # Analysis strategies
    # ------------------------------------------------------------------

    def _general_analysis(self, data: Dict[str, Any]) -> AnalysisResult:
        insights = [f"Data contains {len(data)} top-level keys"]
        return AnalysisResult(
            analysis_type="general",
            insights=insights,
            confidence=0.7,
        )

    def _statistical_analysis(self, data: Dict[str, Any]) -> AnalysisResult:
        numeric_values = [v for v in data.values() if isinstance(v, (int, float))]
        stats: Dict[str, Any] = {}
        if numeric_values:
            stats["count"] = len(numeric_values)
            stats["mean"] = sum(numeric_values) / len(numeric_values)
            stats["min"] = min(numeric_values)
            stats["max"] = max(numeric_values)
        return AnalysisResult(
            analysis_type="statistical",
            statistics=stats,
            insights=[f"Analysed {len(numeric_values)} numeric values"],
            confidence=0.85,
        )

    def _pattern_analysis(self, data: Dict[str, Any]) -> AnalysisResult:
        patterns = [f"Key pattern: '{k}'" for k in list(data.keys())[:5]]
        return AnalysisResult(
            analysis_type="pattern",
            patterns=patterns,
            confidence=0.75,
        )

    def _sentiment_analysis(self, data: Dict[str, Any]) -> AnalysisResult:
        text = str(data.get("text", ""))
        positive_words = {"good", "great", "excellent", "positive", "best"}
        negative_words = {"bad", "poor", "negative", "worst", "terrible"}
        words = set(text.lower().split())
        pos = len(words & positive_words)
        neg = len(words & negative_words)
        sentiment = "positive" if pos > neg else ("negative" if neg > pos else "neutral")
        return AnalysisResult(
            analysis_type="sentiment",
            insights=[f"Overall sentiment: {sentiment}"],
            statistics={"positive_count": pos, "negative_count": neg},
            confidence=0.65,
        )
