"""Error handler — error classification and recovery plan generation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ERROR_TYPES = {
    "resource": ["memory", "cpu", "disk", "quota", "limit"],
    "permission": ["permission", "forbidden", "unauthorized", "access denied"],
    "network": ["timeout", "connection", "network", "socket", "dns"],
    "data": ["inconsistent", "corrupt", "invalid", "format", "schema"],
}


@dataclass
class ErrorAnalysis:
    """Structured analysis of an error."""

    error_type: str
    severity: str  # low | medium | high | critical
    is_recoverable: bool
    root_cause: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryPlan:
    """Steps to recover from an error."""

    error_type: str
    steps: List[str] = field(default_factory=list)
    fallback: Optional[str] = None
    should_retry: bool = True
    retry_delay_seconds: int = 5


class ErrorHandler:
    """Classifies errors and generates recovery plans."""

    def analyze_error(
        self, error: Exception, task: Dict[str, Any]
    ) -> ErrorAnalysis:
        """Analyse *error* in the context of *task*."""
        error_msg = str(error).lower()
        error_type = self._classify(error_msg)
        severity = self._assess_severity(error_type, task)
        recoverable = error_type in ("resource", "network", "data")

        return ErrorAnalysis(
            error_type=error_type,
            severity=severity,
            is_recoverable=recoverable,
            root_cause=str(error),
            context={"task_id": task.get("task_id"), "action": task.get("action")},
        )

    def create_recovery_plan(
        self, task: Dict[str, Any], error: Exception
    ) -> RecoveryPlan:
        """Generate a recovery plan for *error*."""
        analysis = self.analyze_error(error, task)
        builder = {
            "resource": self._resource_recovery,
            "permission": self._permission_recovery,
            "network": self._network_recovery,
            "data": self._data_recovery,
        }.get(analysis.error_type, self._generic_recovery)

        plan = builder(task, analysis)
        logger.info(
            "Recovery plan for task '%s': type=%s steps=%d",
            task.get("task_id"),
            analysis.error_type,
            len(plan.steps),
        )
        return plan

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(self, error_msg: str) -> str:
        for etype, keywords in _ERROR_TYPES.items():
            if any(kw in error_msg for kw in keywords):
                return etype
        return "unknown"

    def _assess_severity(
        self, error_type: str, task: Dict[str, Any]
    ) -> str:
        if error_type == "permission":
            return "high"
        if error_type == "network":
            return "medium"
        if task.get("critical", False):
            return "critical"
        return "low"

    # ------------------------------------------------------------------
    # Recovery builders
    # ------------------------------------------------------------------

    def _resource_recovery(
        self, task: Dict[str, Any], analysis: ErrorAnalysis
    ) -> RecoveryPlan:
        return RecoveryPlan(
            error_type="resource_unavailable",
            steps=[
                "Release unused resources",
                "Reduce task parallelism",
                "Retry with lower resource requirements",
            ],
            should_retry=True,
            retry_delay_seconds=10,
        )

    def _permission_recovery(
        self, task: Dict[str, Any], analysis: ErrorAnalysis
    ) -> RecoveryPlan:
        return RecoveryPlan(
            error_type="permission_denied",
            steps=[
                "Verify API keys and credentials",
                "Check required permissions for task",
                "Escalate to administrator if needed",
            ],
            should_retry=False,
            fallback="Skip task and notify operator",
        )

    def _network_recovery(
        self, task: Dict[str, Any], analysis: ErrorAnalysis
    ) -> RecoveryPlan:
        return RecoveryPlan(
            error_type="network_error",
            steps=[
                "Check network connectivity",
                "Retry with exponential backoff",
                "Switch to backup endpoint if available",
            ],
            should_retry=True,
            retry_delay_seconds=5,
        )

    def _data_recovery(
        self, task: Dict[str, Any], analysis: ErrorAnalysis
    ) -> RecoveryPlan:
        return RecoveryPlan(
            error_type="data_inconsistency",
            steps=[
                "Validate input data schema",
                "Apply data normalisation",
                "Retry with cleaned data",
            ],
            should_retry=True,
            retry_delay_seconds=2,
        )

    def _generic_recovery(
        self, task: Dict[str, Any], analysis: ErrorAnalysis
    ) -> RecoveryPlan:
        return RecoveryPlan(
            error_type="unknown",
            steps=["Log error details", "Retry once with default settings"],
            should_retry=True,
            retry_delay_seconds=3,
        )
