"""Kally AI agent — closed-loop feedback and continuous improvement system."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.agents.base_agent import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class FeedbackSignal:
    """A single feedback observation ingested by Kally."""

    signal_id: str = ""
    source: str = ""
    metric: str = ""
    value: float = 0.0
    threshold: float = 0.0
    severity: str = "info"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClosedLoopReport:
    """Consolidated Kally analysis and improvement recommendations."""

    report_id: str = ""
    signals_analysed: int = 0
    anomalies_detected: int = 0
    recommendations: List[str] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    health_score: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class KallyAgent(BaseAgent):
    """Kally AI — closed-loop system for continuous platform monitoring and self-improvement.

    Kally ingests feedback signals from agents, tools, and infrastructure,
    detects anomalies, and emits actionable recommendations to close the
    improvement loop automatically.

    Supported actions: ``analyse``, ``ingest``, ``report``, ``reset``.
    """

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent)
        self._signal_buffer: List[FeedbackSignal] = []
        self._action_log: List[str] = []

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a Kally AI task."""
        action = task.get("action", "analyse")
        logger.info("KallyAgent action='%s'", action)

        dispatcher = {
            "analyse": self._handle_analyse,
            "ingest": self._handle_ingest,
            "report": self._handle_report,
            "reset": self._handle_reset,
        }
        handler = dispatcher.get(action)
        if handler is None:
            result: Dict[str, Any] = {
                "status": "error",
                "error": f"Unknown action '{action}'",
            }
        else:
            result = await handler(task)

        self._record_task(task, result)
        return result

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def ingest_signal(self, signal: FeedbackSignal) -> None:
        """Ingest a feedback signal into the Kally buffer."""
        self._signal_buffer.append(signal)
        logger.debug("KallyAgent: ingested signal from '%s' metric='%s'", signal.source, signal.metric)

    async def run_closed_loop(self) -> ClosedLoopReport:
        """Execute a full closed-loop analysis cycle."""
        report = await self._analyse_signals()
        await self._apply_recommendations(report)
        return report

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    async def _handle_ingest(self, task: Dict[str, Any]) -> Dict[str, Any]:
        signal = FeedbackSignal(
            signal_id=task.get("signal_id", ""),
            source=task.get("source", "unknown"),
            metric=task.get("metric", ""),
            value=float(task.get("value", 0.0)),
            threshold=float(task.get("threshold", 0.0)),
            severity=task.get("severity", "info"),
            metadata=task.get("metadata", {}),
        )
        await self.ingest_signal(signal)
        return {
            "status": "completed",
            "action": "ingest",
            "buffer_size": len(self._signal_buffer),
        }

    async def _handle_analyse(self, task: Dict[str, Any]) -> Dict[str, Any]:
        report = await self.run_closed_loop()
        return {
            "status": "completed",
            "action": "analyse",
            "signals_analysed": report.signals_analysed,
            "anomalies_detected": report.anomalies_detected,
            "recommendations": report.recommendations,
            "actions_taken": report.actions_taken,
            "health_score": report.health_score,
            "timestamp": report.timestamp,
        }

    async def _handle_report(self, _task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "completed",
            "action": "report",
            "buffered_signals": len(self._signal_buffer),
            "action_log": list(self._action_log[-20:]),
            "health_score": self._compute_health_score(),
        }

    async def _handle_reset(self, _task: Dict[str, Any]) -> Dict[str, Any]:
        cleared = len(self._signal_buffer)
        self._signal_buffer.clear()
        self._action_log.clear()
        return {"status": "completed", "action": "reset", "signals_cleared": cleared}

    # ------------------------------------------------------------------
    # Core analysis engine
    # ------------------------------------------------------------------

    async def _analyse_signals(self) -> ClosedLoopReport:
        signals = list(self._signal_buffer)
        anomalies: List[FeedbackSignal] = []
        recommendations: List[str] = []

        for sig in signals:
            if sig.threshold > 0 and sig.value > sig.threshold:
                anomalies.append(sig)
                recommendations.append(
                    f"[{sig.severity.upper()}] '{sig.metric}' from '{sig.source}' "
                    f"exceeded threshold ({sig.value:.2f} > {sig.threshold:.2f})."
                )

        if not signals:
            recommendations.append("No signals buffered. Increase observability coverage.")

        health = self._compute_health_score()
        if health < 0.8:
            recommendations.append("Overall health below 80% — review anomalous services.")

        return ClosedLoopReport(
            signals_analysed=len(signals),
            anomalies_detected=len(anomalies),
            recommendations=recommendations,
            health_score=health,
        )

    async def _apply_recommendations(self, report: ClosedLoopReport) -> None:
        """Record auto-applied actions from recommendations."""
        for rec in report.recommendations:
            action_entry = f"[{datetime.now(timezone.utc).isoformat()}] AUTO: {rec[:120]}"
            self._action_log.append(action_entry)
            report.actions_taken.append(action_entry)
        logger.info(
            "KallyAgent: closed-loop cycle complete — %d signals, %d anomalies, health=%.2f",
            report.signals_analysed,
            report.anomalies_detected,
            report.health_score,
        )

    def _compute_health_score(self) -> float:
        """Derive a [0, 1] health score from the current signal buffer."""
        if not self._signal_buffer:
            return 1.0
        breach_count = sum(
            1
            for s in self._signal_buffer
            if s.threshold > 0 and s.value > s.threshold
        )
        ratio = breach_count / len(self._signal_buffer)
        return round(max(0.0, 1.0 - ratio), 3)
