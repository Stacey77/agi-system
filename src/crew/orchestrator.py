"""CrewAI orchestrator — coordinates multiple agents on a shared objective."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CrewOrchestrator:
    """Runs a multi-agent crew using CrewAI (falls back to sequential execution if unavailable)."""

    def __init__(self, agent_factory: Any, llm: Optional[Any] = None) -> None:
        self._factory = agent_factory
        self._llm = llm

    async def run(
        self,
        objective: str,
        agent_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute *objective* using a collaborative crew.

        Parameters
        ----------
        objective:
            High-level goal for the crew to accomplish.
        agent_names:
            Agents to include. Defaults to the standard pipeline
            (research → analysis → writing → review).
        """
        if agent_names is None:
            agent_names = ["research_agent", "analysis_agent", "writing_agent", "review_agent"]

        langgraph_result = await self._try_langgraph(objective, agent_names)
        if langgraph_result is not None:
            return langgraph_result

        crewai_result = await self._try_crewai(objective, agent_names)
        if crewai_result is not None:
            return crewai_result

        return await self._sequential_fallback(objective, agent_names)

    # ------------------------------------------------------------------
    # LangGraph path
    # ------------------------------------------------------------------

    async def _try_langgraph(
        self, objective: str, agent_names: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Attempt to run the crew via LangGraph StateGraph; return None if unavailable."""
        try:
            from src.crew.langgraph_orchestrator import run_langgraph_crew
            return await run_langgraph_crew(objective, agent_names, self._factory)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LangGraph path failed: %s — falling back", exc)
            return None

    # ------------------------------------------------------------------
    # CrewAI path
    # ------------------------------------------------------------------

    async def _try_crewai(
        self, objective: str, agent_names: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Attempt to run the crew via CrewAI; return None if unavailable."""
        try:
            from crewai import Agent, Crew, Process, Task  # type: ignore
        except ImportError:
            logger.info("crewai not installed — falling back to sequential execution")
            return None

        agents_map = {n: self._factory.get_agent(n) for n in agent_names}
        crew_agents = []
        for name, agt in agents_map.items():
            if agt is None:
                continue
            crew_agents.append(
                Agent(
                    role=agt.config.agent_type.value.title(),
                    goal=agt.config.description or f"Complete tasks as a {agt.config.agent_type.value} agent",
                    backstory=f"An expert {agt.config.agent_type.value} agent in an AGI system.",
                    llm=self._llm,
                    verbose=False,
                    allow_delegation=False,
                )
            )

        if not crew_agents:
            return None

        tasks = [
            Task(
                description=objective,
                agent=crew_agents[0],
                expected_output="A detailed result addressing the objective",
            )
        ]
        for i, agent in enumerate(crew_agents[1:], 1):
            tasks.append(
                Task(
                    description=f"Build on previous results to further address: {objective}",
                    agent=agent,
                    expected_output="Refined and extended result",
                )
            )

        try:
            crew = Crew(
                agents=crew_agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=False,
            )
            import asyncio
            result = await asyncio.to_thread(crew.kickoff)
            return {
                "status": "completed",
                "engine": "crewai",
                "objective": objective,
                "agents_used": agent_names,
                "result": str(result),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("CrewAI execution failed: %s — falling back", exc)
            return None

    # ------------------------------------------------------------------
    # Sequential fallback
    # ------------------------------------------------------------------

    async def _sequential_fallback(
        self, objective: str, agent_names: List[str]
    ) -> Dict[str, Any]:
        """Run agents sequentially, passing context forward."""
        context = objective
        step_results: List[Dict[str, Any]] = []

        for name in agent_names:
            agent = self._factory.get_agent(name)
            if agent is None:
                logger.warning("Agent '%s' not found — skipping", name)
                continue
            try:
                task = {"task": context}
                result = await agent.process_task(task)
                step_results.append({"agent": name, "result": result})
                # Pass summary forward as context for next agent
                for key in ("summary", "content", "analysis", "code"):
                    if key in result:
                        context = f"{objective}\n\nPrevious output: {result[key]}"
                        break
            except Exception as exc:  # noqa: BLE001
                logger.error("Agent '%s' failed: %s", name, exc)
                step_results.append({"agent": name, "error": str(exc)})

        final = step_results[-1]["result"] if step_results and "result" in step_results[-1] else {}
        return {
            "status": "completed",
            "engine": "sequential",
            "objective": objective,
            "agents_used": agent_names,
            "steps": step_results,
            "result": final,
        }
