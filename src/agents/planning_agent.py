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

    # Maps agent type strings to registered agent names
    _AGENT_TYPE_MAP = {
        "research": "research_agent",
        "analysis": "analysis_agent",
        "writing": "writing_agent",
        "review": "review_agent",
        "coding": "coding_agent",
        "summarization": "summarization_agent",
        "planning": "planning_agent",
    }

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
        llm: Optional[Any] = None,
    ) -> None:
        super().__init__(config, execution_agent, llm)
        self._agent_factory: Optional[Any] = None

    def set_agent_factory(self, factory: Any) -> None:
        """Inject the agent factory to enable step delegation."""
        self._agent_factory = factory

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a planning task — decompose objective into steps."""
        objective = task.get("objective", task.get("task", ""))
        execute = task.get("execute", False)
        logger.info("PlanningAgent processing objective: %s (execute=%s)", objective, execute)

        plan = await self.create_executable_plan(objective)

        result: Dict[str, Any] = {
            "status": "completed",
            "plan": {
                "objective": plan.objective,
                "steps": plan.steps,
                "dependencies": plan.dependencies,
                "is_valid": plan.is_valid,
                "validation_notes": plan.validation_notes,
            },
        }

        if execute and self._agent_factory is not None:
            delegation_results = await self.execute_plan(plan, objective)
            result["delegation_results"] = delegation_results

        self._record_task(task, result)
        return result

    async def execute_plan(
        self, plan: "ExecutablePlan", objective: str
    ) -> List[Dict[str, Any]]:
        """Delegate each plan step to the appropriate agent and collect results."""
        step_results: List[Dict[str, Any]] = []
        context = objective

        for step in plan.steps:
            step_id = step.get("step_id", "")
            agent_type = step.get("agent", "")
            description = step.get("description", step.get("action", ""))
            agent_name = self._AGENT_TYPE_MAP.get(agent_type, f"{agent_type}_agent")
            agent = self._agent_factory.get_agent(agent_name)

            if agent is None:
                logger.warning("Delegation: agent '%s' not found for step %s", agent_name, step_id)
                step_results.append({"step_id": step_id, "agent": agent_name, "error": "agent not found"})
                continue

            try:
                task_dict = {"task": f"{description}\n\nContext: {context}"}
                sub_result = await agent.process_task(task_dict)
                step_results.append({"step_id": step_id, "agent": agent_name, "result": sub_result})
                # Pass summary forward as context
                for key in ("summary", "content", "analysis", "code", "review"):
                    if key in sub_result:
                        context = f"{objective}\n\nPrevious output ({step_id}): {sub_result[key]}"
                        break
            except Exception as exc:  # noqa: BLE001
                logger.error("Delegation error for step %s via '%s': %s", step_id, agent_name, exc)
                step_results.append({"step_id": step_id, "agent": agent_name, "error": str(exc)})

        return step_results

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
