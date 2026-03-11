"""Execution agent — central coordinator for task validation and execution.

Priority score: 9.7 — the highest-priority capability in the AGI system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.execution.execution_engine import ExecutionEngine, ExecutionResult, ExecutionStatus
from src.execution.task_validation import TaskValidationSystem, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult2:  # alias kept for backward compatibility
    """Aggregate result from an agent plan execution."""

    success: bool
    task_results: List[ExecutionResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionAgent:
    """Central execution coordinator.

    Validates tasks before execution, manages the execution lifecycle, and
    orchestrates execution across an agent crew.

    Priority score: **9.7** — bridges planning and real-world action.
    """

    PRIORITY_SCORE: float = 9.7

    def __init__(self, execution_engine: Optional[ExecutionEngine] = None) -> None:
        self._engine = execution_engine or ExecutionEngine()
        self._validator = TaskValidationSystem()
        logger.info(
            "ExecutionAgent initialised (priority=%.1f)", self.PRIORITY_SCORE
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def execute_plan(self, agent_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and execute *agent_plan*.

        Parameters
        ----------
        agent_plan:
            A dictionary with at minimum a ``tasks`` list.
        """
        logger.info("ExecutionAgent.execute_plan called")
        validation = await self.validate_plan(agent_plan)
        if not validation.get("is_valid"):
            return {
                "success": False,
                "errors": validation.get("errors", []),
                "task_results": [],
            }

        results = await self._engine.execute_plan(agent_plan)
        errors = [r.error for r in results if r.error]

        return {
            "success": all(r.status == ExecutionStatus.COMPLETED for r in results),
            "task_results": [
                {
                    "task_id": r.task_id,
                    "status": r.status,
                    "result": r.result,
                    "execution_time": r.execution_time,
                    "error": r.error,
                }
                for r in results
            ],
            "errors": errors,
        }

    async def orchestrate_execution(
        self, plan: Dict[str, Any], crew: Any
    ) -> Dict[str, Any]:
        """Orchestrate execution across a CrewAI *crew*.

        If crew supports a ``kickoff`` method it will be invoked;
        otherwise falls back to direct plan execution.
        """
        logger.info("ExecutionAgent orchestrating crew execution")
        try:
            if hasattr(crew, "kickoff"):
                crew_result = crew.kickoff(inputs=plan)
                return {"success": True, "crew_result": str(crew_result), "errors": []}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Crew kickoff failed, falling back: %s", exc)

        return await self.execute_plan(plan)

    async def validate_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Validate *plan* and return a validation summary."""
        tasks = plan.get("tasks", [])
        all_errors: List[str] = []
        all_warnings: List[str] = []

        for task in tasks:
            result: ValidationResult = self._validator.validate_task(task)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

        is_valid = len(all_errors) == 0
        return {
            "is_valid": is_valid,
            "errors": all_errors,
            "warnings": all_warnings,
            "notes": all_warnings,
        }
