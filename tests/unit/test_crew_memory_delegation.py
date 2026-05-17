"""Unit tests for CrewAI orchestration, TaskMemory, and agent delegation."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base_agent import AgentConfig, AgentType, BaseAgent
from src.agents.planning_agent import ExecutablePlan, PlanningAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(name: str, agent_type: AgentType = AgentType.RESEARCH) -> AgentConfig:
    return AgentConfig(name=name, agent_type=agent_type)


class _SimpleAgent(BaseAgent):
    """Minimal concrete agent for testing."""

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "summary": f"done: {task.get('task', '')}"}


# ---------------------------------------------------------------------------
# TaskMemory
# ---------------------------------------------------------------------------

class TestTaskMemory:
    def test_remember_and_recall(self):
        """TaskMemory stores tasks and retrieves them via similarity search."""
        from src.memory.task_memory import TaskMemory

        mem = TaskMemory(agent_name="test_agent")
        task = {"task": "summarise quarterly report"}
        result = {"status": "completed", "summary": "Q3 revenue up 12%"}
        mem.remember(task, result)
        assert len(mem) == 1

    def test_recall_returns_list(self):
        from src.memory.task_memory import TaskMemory

        mem = TaskMemory(agent_name="recall_agent")
        mem.remember({"task": "analyse sales data"}, {"status": "done", "analysis": "growth"})
        hits = mem.recall("sales analysis", k=1)
        assert isinstance(hits, list)

    def test_recall_empty(self):
        from src.memory.task_memory import TaskMemory

        mem = TaskMemory(agent_name="empty_agent")
        hits = mem.recall("anything")
        assert hits == []

    def test_multiple_memories(self):
        from src.memory.task_memory import TaskMemory

        mem = TaskMemory(agent_name="multi_agent")
        for i in range(5):
            mem.remember({"task": f"task {i}"}, {"status": "done", "result": i})
        assert len(mem) == 5


# ---------------------------------------------------------------------------
# BaseAgent persistent memory integration
# ---------------------------------------------------------------------------

class TestBaseAgentPersistMemory:
    def test_persist_memory_disabled_by_default(self):
        config = _make_config("no_persist")
        agent = _SimpleAgent(config)
        assert agent._task_memory is None

    def test_recall_returns_empty_without_persist(self):
        config = _make_config("no_persist2")
        agent = _SimpleAgent(config)
        assert agent.recall_similar_tasks("anything") == []

    def test_persist_memory_enabled(self):
        config = _make_config("persist_agent")
        with patch("src.memory.task_memory.TaskMemory") as MockMem:
            mock_mem = MagicMock()
            MockMem.return_value = mock_mem
            agent = _SimpleAgent(config, persist_memory=True)
            assert agent._task_memory is mock_mem

    def test_record_task_calls_task_memory(self):
        config = _make_config("record_agent")
        agent = _SimpleAgent(config)
        mock_mem = MagicMock()
        agent._task_memory = mock_mem
        task = {"task": "do something"}
        result = {"status": "done"}
        agent._record_task(task, result)
        mock_mem.remember.assert_called_once_with(task, result)

    def test_recall_delegates_to_task_memory(self):
        config = _make_config("recall_delegate")
        agent = _SimpleAgent(config)
        mock_mem = MagicMock()
        mock_mem.recall.return_value = [{"task": "old task", "result": {}}]
        agent._task_memory = mock_mem
        results = agent.recall_similar_tasks("old task", k=1)
        mock_mem.recall.assert_called_once_with("old task", k=1)
        assert len(results) == 1

    def test_get_status_includes_persistent_memory_size(self):
        config = _make_config("status_agent")
        agent = _SimpleAgent(config)
        mock_mem = MagicMock()
        mock_mem.__len__ = MagicMock(return_value=7)
        agent._task_memory = mock_mem
        status = agent.get_status()
        assert status["persistent_memory_size"] == 7


# ---------------------------------------------------------------------------
# CrewOrchestrator (sequential fallback — no crewai dependency)
# ---------------------------------------------------------------------------

class TestCrewOrchestrator:
    def _make_factory(self, agents: Dict[str, BaseAgent]):
        factory = MagicMock()
        factory.get_agent.side_effect = lambda name: agents.get(name)
        return factory

    @pytest.mark.asyncio
    async def test_sequential_fallback_runs_all_agents(self):
        from src.crew.orchestrator import CrewOrchestrator

        research = _SimpleAgent(_make_config("research_agent", AgentType.RESEARCH))
        analysis = _SimpleAgent(_make_config("analysis_agent", AgentType.ANALYSIS))
        factory = self._make_factory({"research_agent": research, "analysis_agent": analysis})

        orch = CrewOrchestrator(agent_factory=factory)
        result = await orch._sequential_fallback("test objective", ["research_agent", "analysis_agent"])

        assert result["status"] == "completed"
        assert result["engine"] == "sequential"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["agent"] == "research_agent"

    @pytest.mark.asyncio
    async def test_skips_missing_agents(self):
        from src.crew.orchestrator import CrewOrchestrator

        real = _SimpleAgent(_make_config("analysis_agent", AgentType.ANALYSIS))
        factory = self._make_factory({"analysis_agent": real})

        orch = CrewOrchestrator(agent_factory=factory)
        result = await orch._sequential_fallback(
            "obj", ["missing_agent", "analysis_agent"]
        )
        assert len(result["steps"]) == 1
        assert result["steps"][0]["agent"] == "analysis_agent"

    @pytest.mark.asyncio
    async def test_run_falls_back_when_crewai_missing(self):
        from src.crew.orchestrator import CrewOrchestrator

        research = _SimpleAgent(_make_config("research_agent", AgentType.RESEARCH))
        factory = self._make_factory({"research_agent": research})

        orch = CrewOrchestrator(agent_factory=factory)
        with patch.dict("sys.modules", {"crewai": None}):
            result = await orch.run("objective", agent_names=["research_agent"])
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_context_passes_between_steps(self):
        """Summary from step N is passed as context to step N+1."""
        from src.crew.orchestrator import CrewOrchestrator

        calls: List[Dict] = []

        class _TrackingAgent(BaseAgent):
            async def process_task(self, task):
                calls.append(task)
                return {"status": "done", "summary": "step summary"}

        a1 = _TrackingAgent(_make_config("a1"))
        a2 = _TrackingAgent(_make_config("a2"))
        factory = self._make_factory({"a1": a1, "a2": a2})

        orch = CrewOrchestrator(agent_factory=factory)
        await orch._sequential_fallback("base objective", ["a1", "a2"])

        assert "Previous output" in calls[1]["task"]


# ---------------------------------------------------------------------------
# PlanningAgent delegation
# ---------------------------------------------------------------------------

class TestPlanningAgentDelegation:
    def _make_planning_agent(self) -> PlanningAgent:
        config = AgentConfig(
            name="planning_agent",
            agent_type=AgentType.PLANNING,
        )
        return PlanningAgent(config=config)

    def _make_factory(self, agents):
        factory = MagicMock()
        factory.get_agent.side_effect = lambda name: agents.get(name)
        return factory

    def test_set_agent_factory(self):
        agent = self._make_planning_agent()
        factory = MagicMock()
        agent.set_agent_factory(factory)
        assert agent._agent_factory is factory

    @pytest.mark.asyncio
    async def test_execute_plan_delegates_to_agents(self):
        agent = self._make_planning_agent()
        research = _SimpleAgent(_make_config("research_agent", AgentType.RESEARCH))
        analysis = _SimpleAgent(_make_config("analysis_agent", AgentType.ANALYSIS))
        factory = self._make_factory(
            {"research_agent": research, "analysis_agent": analysis}
        )
        agent.set_agent_factory(factory)

        plan = ExecutablePlan(
            objective="test objective",
            steps=[
                {"step_id": "step_1", "action": "research", "description": "gather info", "agent": "research"},
                {"step_id": "step_2", "action": "analyse", "description": "analyse it", "agent": "analysis"},
            ],
        )
        results = await agent.execute_plan(plan, "test objective")
        assert len(results) == 2
        assert results[0]["step_id"] == "step_1"
        assert results[0]["agent"] == "research_agent"
        assert "result" in results[0]

    @pytest.mark.asyncio
    async def test_execute_plan_handles_missing_agent(self):
        agent = self._make_planning_agent()
        factory = self._make_factory({})
        agent.set_agent_factory(factory)

        plan = ExecutablePlan(
            objective="obj",
            steps=[
                {"step_id": "step_1", "action": "research", "description": "d", "agent": "research"},
            ],
        )
        results = await agent.execute_plan(plan, "obj")
        assert results[0]["error"] == "agent not found"

    @pytest.mark.asyncio
    async def test_process_task_with_execute_flag(self):
        agent = self._make_planning_agent()
        research = _SimpleAgent(_make_config("research_agent", AgentType.RESEARCH))
        analysis = _SimpleAgent(_make_config("analysis_agent", AgentType.ANALYSIS))
        writing = _SimpleAgent(_make_config("writing_agent", AgentType.WRITING))
        review = _SimpleAgent(_make_config("review_agent", AgentType.REVIEW))
        factory = self._make_factory({
            "research_agent": research,
            "analysis_agent": analysis,
            "writing_agent": writing,
            "review_agent": review,
        })
        agent.set_agent_factory(factory)

        result = await agent.process_task({"task": "build a report", "execute": True})
        assert "delegation_results" in result
        assert isinstance(result["delegation_results"], list)

    @pytest.mark.asyncio
    async def test_process_task_no_execute_no_delegation(self):
        agent = self._make_planning_agent()
        result = await agent.process_task({"task": "plan something"})
        assert "delegation_results" not in result
        assert "plan" in result
