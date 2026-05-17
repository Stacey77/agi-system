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

    _SYSTEM_PROMPT = (
        "You are a strategic planning agent. Given an objective, decompose it into a "
        "numbered list of concrete, actionable steps. Each step must include: "
        "step_id (e.g. step_1), action (verb), description, and the best agent type "
        "(planning/research/analysis/writing/review/coding/summarization). "
        "Respond ONLY with a JSON array of step objects."
    )

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
        llm: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent, llm)

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

        Uses the LLM when available; falls back to a hard-coded pipeline otherwise.
        If an execution_agent is available the plan is validated before being returned.
        """
        steps = await self._llm_decompose(objective) or self._decompose_objective(objective)
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

    async def _llm_decompose(self, objective: str) -> Optional[List[Dict[str, Any]]]:
        """Ask the LLM to decompose *objective* into steps. Returns None on failure."""
        import json

        raw = await self._invoke_llm(self._SYSTEM_PROMPT, f"Objective: {objective}")
        if not raw:
            return None
        try:
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            steps: List[Dict[str, Any]] = json.loads(raw)
            if isinstance(steps, list) and steps:
                return steps
        except (json.JSONDecodeError, ValueError):
            logger.warning("LLM returned non-JSON plan; falling back to hardcoded decomposition")
        return None

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
