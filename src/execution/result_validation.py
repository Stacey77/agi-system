"""Result validation — post-execution quality assessment."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class QualityAssessment:
    """Quality assessment of an execution result."""

    completeness: float
    accuracy: float
    consistency: float
    safety: float
    is_valid: bool

    @property
    def overall_score(self) -> float:
        return (
            self.completeness * 0.3
            + self.accuracy * 0.3
            + self.consistency * 0.2
            + self.safety * 0.2
        )


class ResultValidationSystem:
    """Validates and scores execution results."""

    def validate_result(
        self, task: Dict[str, Any], result: Any
    ) -> QualityAssessment:
        """Assess the quality of *result* relative to *task*."""
        completeness = self._score_completeness(task, result)
        accuracy = self._score_accuracy(task, result)
        consistency = self._score_consistency(task, result)
        safety = self._score_safety(result)
        is_valid = all(s >= 0.4 for s in (completeness, accuracy, consistency, safety))

        assessment = QualityAssessment(
            completeness=completeness,
            accuracy=accuracy,
            consistency=consistency,
            safety=safety,
            is_valid=is_valid,
        )
        logger.debug(
            "Quality assessment for task '%s': score=%.2f valid=%s",
            task.get("task_id", "?"),
            assessment.overall_score,
            is_valid,
        )
        return assessment

    # ------------------------------------------------------------------
    # Scoring methods
    # ------------------------------------------------------------------

    def _score_completeness(self, task: Dict[str, Any], result: Any) -> float:
        if result is None:
            return 0.0
        required_fields = task.get("required_output_fields", [])
        if not required_fields:
            return 1.0 if result else 0.0
        if isinstance(result, dict):
            present = sum(1 for f in required_fields if f in result)
            return present / len(required_fields)
        return 0.8

    def _score_accuracy(self, task: Dict[str, Any], result: Any) -> float:
        # Without a ground-truth oracle we return a conservative default
        if isinstance(result, dict) and result.get("error"):
            return 0.3
        return 0.8

    def _score_consistency(self, task: Dict[str, Any], result: Any) -> float:
        if isinstance(result, dict):
            # Check that result type matches expected type if specified
            expected_type = task.get("expected_result_type")
            _ALLOWED_TYPES: Dict[str, type] = {
                "dict": dict,
                "list": list,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
            }
            if expected_type and expected_type in _ALLOWED_TYPES:
                if not isinstance(result.get("result"), _ALLOWED_TYPES[expected_type]):
                    return 0.5
        return 0.9

    def _score_safety(self, result: Any) -> float:
        if isinstance(result, str):
            dangerous_patterns = ["password", "secret", "token", "api_key"]
            for pattern in dangerous_patterns:
                if pattern in result.lower():
                    return 0.3
        return 1.0
