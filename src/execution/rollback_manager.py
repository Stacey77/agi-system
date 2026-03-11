"""Rollback manager — checkpoint-based rollback for task sequences."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """A saved state snapshot."""

    checkpoint_id: str
    state: Dict[str, Any]
    completed_steps: List[str] = field(default_factory=list)


@dataclass
class RollbackResult:
    """Result of an execute-with-rollback operation."""

    success: bool
    completed_tasks: List[str] = field(default_factory=list)
    rolled_back_to: Optional[str] = None
    error: Optional[str] = None


class RollbackPlan:
    """Manages checkpoints and performs rollbacks."""

    def __init__(self) -> None:
        self._checkpoints: List[Checkpoint] = []

    def add_checkpoint(
        self, checkpoint_id: str, state: Dict[str, Any], completed_steps: List[str]
    ) -> None:
        self._checkpoints.append(
            Checkpoint(
                checkpoint_id=checkpoint_id,
                state=state,
                completed_steps=list(completed_steps),
            )
        )
        logger.debug("Checkpoint added: %s", checkpoint_id)

    def perform_rollback(self, target_id: Optional[str] = None) -> Optional[Checkpoint]:
        """Roll back to *target_id* or the most recent checkpoint."""
        if not self._checkpoints:
            return None
        if target_id is None:
            cp = self._checkpoints[-1]
        else:
            cp = next(
                (c for c in reversed(self._checkpoints) if c.checkpoint_id == target_id),
                self._checkpoints[-1],
            )
        logger.info("Rolling back to checkpoint '%s'", cp.checkpoint_id)
        return cp

    def latest_checkpoint(self) -> Optional[Checkpoint]:
        return self._checkpoints[-1] if self._checkpoints else None


class RollbackManager:
    """Executes task sequences with automatic rollback on failure."""

    def __init__(self) -> None:
        self._rollback_plan = RollbackPlan()

    async def execute_with_rollback(
        self,
        task_sequence: List[Dict[str, Any]],
        executor: Optional[Callable[..., Any]] = None,
    ) -> RollbackResult:
        """Execute *task_sequence*, rolling back on failure.

        Parameters
        ----------
        task_sequence:
            Ordered list of task dictionaries.
        executor:
            Optional async callable that executes a single task dict.
            Defaults to a no-op that marks each task as completed.
        """
        completed: List[str] = []
        state: Dict[str, Any] = {}

        for task in task_sequence:
            task_id = task.get("task_id", f"task_{len(completed)}")
            try:
                if executor is not None:
                    result = await executor(task)
                    state[task_id] = result
                else:
                    state[task_id] = {"status": "completed"}

                completed.append(task_id)
                self._rollback_plan.add_checkpoint(
                    checkpoint_id=f"cp_{task_id}",
                    state=dict(state),
                    completed_steps=list(completed),
                )
                logger.debug("Task '%s' completed successfully", task_id)

            except Exception as exc:  # noqa: BLE001
                logger.error("Task '%s' failed: %s — rolling back", task_id, exc)
                cp = self._rollback_plan.perform_rollback()
                rolled_back_to = cp.checkpoint_id if cp else None
                return RollbackResult(
                    success=False,
                    completed_tasks=completed,
                    rolled_back_to=rolled_back_to,
                    error=str(exc),
                )

        return RollbackResult(success=True, completed_tasks=completed)
