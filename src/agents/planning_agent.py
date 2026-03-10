"""Planning agent — task decomposition and dependency analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base_agent import AgentConfig, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class ExecutablePlan:
    """Represents a validated, executable plan."""

    objective: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    validation_notes: List[str] = field(default_factory=list)


class PlanningAgent(BaseAgent):
    """Decomposes high-level objectives into executable plans."""

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent)

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a planning task — decompose objective into steps."""
        objective = task.get("objective", task.get("task", ""))
        logger.info("PlanningAgent processing objective: %s", objective)

        plan = await self.create_executable_plan(objective)

        result = {
            "status": "completed",
            "plan": {
                "objective": plan.objective,
                "steps": plan.steps,
                "dependencies": plan.dependencies,
                "is_valid": plan.is_valid,
                "validation_notes": plan.validation_notes,
            },
        }
        self._record_task(task, result)
        return result

    async def create_executable_plan(self, objective: str) -> ExecutablePlan:
        """Decompose an objective into an executable plan.

        If an execution_agent is available the plan is validated before
        being returned; otherwise a best-effort plan is returned directly.
        """
        steps = self._decompose_objective(objective)
        dependencies = self._analyse_dependencies(steps)

        plan = ExecutablePlan(
            objective=objective,
            steps=steps,
            dependencies=dependencies,
        )

        if self.execution_agent is not None:
            try:
                validation = await self.execution_agent.validate_plan(
                    {"objective": objective, "steps": steps}
                )
                plan.is_valid = validation.get("is_valid", True)
                plan.validation_notes = validation.get("notes", [])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Plan validation failed: %s", exc)

        return plan

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _decompose_objective(self, objective: str) -> List[Dict[str, Any]]:
        """Break an objective into ordered steps."""
        return [
            {
                "step_id": "step_1",
                "action": "research",
                "description": f"Gather information related to: {objective}",
                "agent": "research",
            },
            {
                "step_id": "step_2",
                "action": "analyse",
                "description": "Analyse gathered information",
                "agent": "analysis",
            },
            {
                "step_id": "step_3",
                "action": "synthesise",
                "description": "Synthesise findings into output",
                "agent": "writing",
            },
            {
                "step_id": "step_4",
                "action": "review",
                "description": "Review and validate output quality",
                "agent": "review",
            },
        ]

    def _analyse_dependencies(
        self, steps: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Build a simple sequential dependency graph."""
        deps: Dict[str, List[str]] = {}
        for i, step in enumerate(steps):
            step_id = step["step_id"]
            deps[step_id] = [steps[i - 1]["step_id"]] if i > 0 else []
        return deps
