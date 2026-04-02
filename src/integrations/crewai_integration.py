"""CrewAI integration — Crew, Task, and Agent factory helpers.

Bridges the AGI system's :class:`~src.agents.base_agent.AgentConfig` layer
with CrewAI's ``Agent``, ``Task``, and ``Crew`` objects.  All CrewAI imports
are guarded so the system degrades gracefully when the library is absent or
no LLM credentials are configured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base_agent import AgentConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CrewRunResult:
    """Result returned by :meth:`CrewBuilder.run`."""

    success: bool
    output: str = ""
    task_outputs: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    used_mock: bool = False


# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------


class CrewAIAgentBuilder:
    """Converts an :class:`AgentConfig` into a CrewAI ``Agent`` object.

    Falls back to a lightweight :class:`_MockCrewAIAgent` when CrewAI is
    not installed or no LLM credentials are available.
    """

    # Role-specific backstories enhance CrewAI's behaviour.
    _BACKSTORIES: Dict[str, str] = {
        "planning": (
            "You are a meticulous project manager with decades of experience "
            "decomposing complex goals into actionable plans."
        ),
        "research": (
            "You are a seasoned investigative researcher skilled at finding "
            "reliable information from diverse sources."
        ),
        "analysis": (
            "You are a data scientist with deep expertise in statistical analysis "
            "and pattern recognition."
        ),
        "writing": (
            "You are a professional writer who crafts clear, engaging content "
            "tailored to any audience or tone."
        ),
        "review": (
            "You are a rigorous quality-assurance specialist who identifies "
            "inaccuracies and ensures outputs meet high standards."
        ),
    }

    def build(self, config: AgentConfig) -> Any:
        """Return a CrewAI Agent (or mock) for *config*."""
        try:
            from crewai import Agent  # type: ignore[import]

            agent = Agent(
                role=config.agent_type.value.replace("_", " ").title(),
                goal=config.description or f"Complete {config.agent_type.value} tasks",
                backstory=self._BACKSTORIES.get(config.agent_type.value, ""),
                verbose=False,
                allow_delegation=False,
            )
            logger.debug("CrewAIAgentBuilder: created real Agent for '%s'", config.name)
            return agent
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "CrewAI Agent creation failed for '%s'; using mock: %s",
                config.name,
                exc,
            )
            return _MockCrewAIAgent(config)


# ---------------------------------------------------------------------------
# Task builder
# ---------------------------------------------------------------------------


class CrewAITaskBuilder:
    """Creates CrewAI ``Task`` objects from plain task dictionaries."""

    def build(
        self,
        task_dict: Dict[str, Any],
        agent: Any,
    ) -> Any:
        """Return a CrewAI Task (or mock) for *task_dict* assigned to *agent*."""
        description = (
            task_dict.get("description")
            or task_dict.get("objective")
            or task_dict.get("task")
            or "Execute the assigned task"
        )
        expected_output = task_dict.get(
            "expected_output", "A comprehensive result addressing the task."
        )
        try:
            from crewai import Task  # type: ignore[import]

            task = Task(
                description=description,
                expected_output=expected_output,
                agent=agent,
            )
            logger.debug("CrewAITaskBuilder: created real Task '%s'", description[:40])
            return task
        except Exception as exc:  # noqa: BLE001
            logger.warning("CrewAI Task creation failed; using mock: %s", exc)
            return _MockCrewAITask(description, expected_output, agent)


# ---------------------------------------------------------------------------
# Crew builder / runner
# ---------------------------------------------------------------------------


class CrewBuilder:
    """Assembles a full CrewAI ``Crew`` from agent configs and tasks, then
    executes it via :meth:`run`.

    Example::

        builder = CrewBuilder()
        result = await builder.run(
            agent_configs=[research_config, writing_config],
            tasks=[
                {"description": "Research recent AI papers"},
                {"description": "Write a summary report"},
            ],
            objective="Summarise the latest AI research",
        )
    """

    def __init__(self) -> None:
        self._agent_builder = CrewAIAgentBuilder()
        self._task_builder = CrewAITaskBuilder()

    async def run(
        self,
        agent_configs: List[AgentConfig],
        tasks: List[Dict[str, Any]],
        objective: str = "",
    ) -> CrewRunResult:
        """Build and run a crew, returning a :class:`CrewRunResult`."""
        if not agent_configs:
            return CrewRunResult(
                success=False, error="No agent configs provided", used_mock=True
            )

        crew_agents = [self._agent_builder.build(cfg) for cfg in agent_configs]
        use_mock = any(isinstance(a, _MockCrewAIAgent) for a in crew_agents)

        # Pair tasks to agents round-robin
        crew_tasks = []
        for i, task_dict in enumerate(tasks):
            agent = crew_agents[i % len(crew_agents)]
            crew_tasks.append(self._task_builder.build(task_dict, agent))

        if use_mock or not tasks:
            return self._mock_run(objective, tasks, crew_agents)

        try:
            from crewai import Crew, Process  # type: ignore[import]

            crew = Crew(
                agents=crew_agents,
                tasks=crew_tasks,
                process=Process.sequential,
                verbose=False,
            )
            raw = crew.kickoff(inputs={"objective": objective})
            task_outputs = [
                {"task": t.description, "output": str(t.output) if hasattr(t, "output") else ""}
                for t in crew_tasks
            ]
            return CrewRunResult(
                success=True,
                output=str(raw),
                task_outputs=task_outputs,
                used_mock=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Crew kickoff failed, returning mock result: %s", exc)
            return self._mock_run(objective, tasks, crew_agents)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_run(
        objective: str,
        tasks: List[Dict[str, Any]],
        agents: List[Any],
    ) -> CrewRunResult:
        agent_names = [
            getattr(a, "role", getattr(a, "_name", "agent")) for a in agents
        ]
        task_outputs = [
            {
                "task": t.get("description", t.get("objective", "task")),
                "output": f"[Mock output for task {i + 1}]",
            }
            for i, t in enumerate(tasks)
        ]
        return CrewRunResult(
            success=True,
            output=(
                f"[Mock crew result] Objective='{objective}' "
                f"agents={agent_names} tasks={len(tasks)}"
            ),
            task_outputs=task_outputs,
            used_mock=True,
        )


# ---------------------------------------------------------------------------
# Mock fallbacks (used when crewai is absent or LLM credentials missing)
# ---------------------------------------------------------------------------


class _MockCrewAIAgent:
    """Lightweight stand-in for a CrewAI Agent."""

    def __init__(self, config: AgentConfig) -> None:
        self._name = config.name
        self.role = config.agent_type.value.replace("_", " ").title()

    def __repr__(self) -> str:
        return f"<MockCrewAIAgent name={self._name!r} role={self.role!r}>"


class _MockCrewAITask:
    """Lightweight stand-in for a CrewAI Task."""

    def __init__(self, description: str, expected_output: str, agent: Any) -> None:
        self.description = description
        self.expected_output = expected_output
        self.agent = agent
        self.output = f"[Mock output for: {description[:60]}]"

    def __repr__(self) -> str:
        return f"<MockCrewAITask description={self.description[:40]!r}>"
