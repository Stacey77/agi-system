"""LangGraph-based crew orchestrator — stateful multi-agent workflow with retry and branching."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """Shared state threaded through the LangGraph workflow."""

    objective: str
    context: str
    agent_names: List[str]
    step_results: List[Dict[str, Any]]
    current_idx: int
    error: str


async def run_langgraph_crew(
    objective: str,
    agent_names: List[str],
    factory: Any,
    max_retries: int = 2,
) -> Optional[Dict[str, Any]]:
    """Execute a crew workflow via LangGraph StateGraph.

    Returns a result dict on success, or None if LangGraph is unavailable.
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        logger.info("langgraph not installed — skipping LangGraph path")
        return None

    if not agent_names:
        return None

    graph: StateGraph = StateGraph(AgentState)

    # Build one node per agent
    for name in agent_names:
        async def _make_node(state: AgentState, _name: str = name) -> AgentState:
            agent = factory.get_agent(_name)
            if agent is None:
                logger.warning("LangGraph: agent '%s' not found — skipping", _name)
                return state

            task_dict = {"task": state["context"]}
            last_exc: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    result = await agent.process_task(task_dict)
                    new_context = state["context"]
                    for key in ("summary", "content", "analysis", "code", "review"):
                        if key in result:
                            new_context = f"{state['objective']}\n\nPrevious ({_name}): {result[key]}"
                            break
                    updated_results = list(state["step_results"]) + [
                        {"agent": _name, "result": result}
                    ]
                    return AgentState(
                        objective=state["objective"],
                        context=new_context,
                        agent_names=state["agent_names"],
                        step_results=updated_results,
                        current_idx=state["current_idx"] + 1,
                        error="",
                    )
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt < max_retries:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        logger.warning(
                            "LangGraph: agent '%s' attempt %d failed: %s — retrying",
                            _name, attempt + 1, exc,
                        )

            logger.error("LangGraph: agent '%s' failed after %d retries: %s", _name, max_retries, last_exc)
            return AgentState(
                objective=state["objective"],
                context=state["context"],
                agent_names=state["agent_names"],
                step_results=list(state["step_results"]) + [
                    {"agent": _name, "error": str(last_exc)}
                ],
                current_idx=state["current_idx"] + 1,
                error=str(last_exc),
            )

        graph.add_node(name, _make_node)

    # Wire edges: linear chain
    graph.set_entry_point(agent_names[0])
    for i in range(len(agent_names) - 1):
        graph.add_edge(agent_names[i], agent_names[i + 1])
    graph.add_edge(agent_names[-1], END)

    try:
        compiled = graph.compile()
        initial_state = AgentState(
            objective=objective,
            context=objective,
            agent_names=agent_names,
            step_results=[],
            current_idx=0,
            error="",
        )
        final_state = await compiled.ainvoke(initial_state)
        step_results: List[Dict[str, Any]] = final_state.get("step_results", [])
        final_result = next(
            (s["result"] for s in reversed(step_results) if "result" in s), {}
        )
        return {
            "status": "completed",
            "engine": "langgraph",
            "objective": objective,
            "agents_used": agent_names,
            "steps": step_results,
            "result": final_result,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("LangGraph execution failed: %s — falling back", exc)
        return None
