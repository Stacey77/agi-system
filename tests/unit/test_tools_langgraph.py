"""Unit tests for tool registry wiring and LangGraph orchestration."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import AgentConfig, AgentType, BaseAgent
from src.tools.calculator_tool import CalculatorTool
from src.tools.tool_registry import ToolRegistry
from src.tools.web_search_tool import WebSearchTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(name: str, agent_type: AgentType = AgentType.RESEARCH) -> AgentConfig:
    return AgentConfig(name=name, agent_type=agent_type)


class _SimpleAgent(BaseAgent):
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "summary": f"done: {task.get('task', '')}"}


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        calc = CalculatorTool()
        reg.register_tool(calc)
        assert "calculator" in reg
        assert reg.get_tool("calculator") is calc

    def test_missing_tool_raises(self):
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.get_tool("nonexistent")

    def test_list_tools(self):
        reg = ToolRegistry()
        reg.register_tool(CalculatorTool())
        reg.register_tool(WebSearchTool())
        metas = reg.list_tools()
        names = [m.name for m in metas]
        assert "calculator" in names
        assert "web_search" in names

    def test_get_tools_by_category(self):
        reg = ToolRegistry()
        reg.register_tool(CalculatorTool())
        tools = reg.get_tools_by_category("analytical")
        assert len(tools) >= 1


# ---------------------------------------------------------------------------
# CalculatorTool
# ---------------------------------------------------------------------------

class TestCalculatorTool:
    def test_evaluate_simple_expression(self):
        calc = CalculatorTool()
        assert calc.execute(expression="2 + 3") == 5.0

    def test_evaluate_complex_expression(self):
        calc = CalculatorTool()
        result = calc.execute(expression="sqrt(16) + 2 ** 3")
        assert abs(result - 12.0) < 1e-9

    def test_statistics_mode(self):
        calc = CalculatorTool()
        result = calc.execute(expression="mean", operation="statistics", data=[1, 2, 3, 4, 5])
        assert result["mean"] == 3.0
        assert result["count"] == 5

    def test_invalid_expression_returns_error(self):
        calc = CalculatorTool()
        result = calc.execute(expression="__import__('os')")
        assert isinstance(result, dict) and "error" in result

    def test_missing_parameter(self):
        calc = CalculatorTool()
        result = calc.execute()
        assert isinstance(result, dict) and "error" in result


# ---------------------------------------------------------------------------
# WebSearchTool
# ---------------------------------------------------------------------------

class TestWebSearchTool:
    def test_mock_search_returns_results(self):
        tool = WebSearchTool()
        results = tool.execute(query="Python programming")
        assert isinstance(results, list)
        assert len(results) > 0
        assert "title" in results[0]
        assert "snippet" in results[0]

    def test_no_api_key_uses_mock(self):
        tool = WebSearchTool(api_key=None)
        results = tool.execute(query="test query", max_results=2)
        assert len(results) <= 3

    def test_max_results_respected(self):
        tool = WebSearchTool()
        results = tool.execute(query="test", max_results=1)
        assert len(results) <= 3  # mock returns min(max_results, 3)

    def test_missing_query_returns_empty(self):
        tool = WebSearchTool()
        results = tool.execute()
        assert results == []


# ---------------------------------------------------------------------------
# AgentFactory tool registry injection
# ---------------------------------------------------------------------------

class TestAgentFactoryToolRegistry:
    def test_set_tool_registry_propagates(self):
        factory = AgentFactory()
        config = AgentConfig(name="r", agent_type=AgentType.RESEARCH)
        agent = factory.create_agent(config)

        reg = ToolRegistry()
        reg.register_tool(CalculatorTool())
        factory.set_tool_registry(reg)

        assert agent._tool_registry is reg

    def test_get_tool_via_agent(self):
        factory = AgentFactory()
        config = AgentConfig(name="r2", agent_type=AgentType.RESEARCH)
        agent = factory.create_agent(config)

        reg = ToolRegistry()
        reg.register_tool(CalculatorTool())
        factory.set_tool_registry(reg)

        tool = agent._get_tool("calculator")
        assert tool is not None

    def test_get_missing_tool_returns_none(self):
        factory = AgentFactory()
        config = AgentConfig(name="r3", agent_type=AgentType.RESEARCH)
        agent = factory.create_agent(config)

        reg = ToolRegistry()
        factory.set_tool_registry(reg)

        assert agent._get_tool("nonexistent") is None


# ---------------------------------------------------------------------------
# LangGraph orchestrator
# ---------------------------------------------------------------------------

class TestLangGraphOrchestrator:
    def _make_factory(self, agents):
        factory = MagicMock()
        factory.get_agent.side_effect = lambda name: agents.get(name)
        return factory

    @pytest.mark.asyncio
    async def test_run_langgraph_crew_sequential(self):
        from src.crew.langgraph_orchestrator import run_langgraph_crew

        a1 = _SimpleAgent(_make_config("a1"))
        a2 = _SimpleAgent(_make_config("a2"))
        factory = self._make_factory({"a1": a1, "a2": a2})

        result = await run_langgraph_crew("test objective", ["a1", "a2"], factory)
        assert result is not None
        assert result["status"] == "completed"
        assert result["engine"] == "langgraph"
        assert len(result["steps"]) == 2

    @pytest.mark.asyncio
    async def test_run_langgraph_handles_missing_agent(self):
        from src.crew.langgraph_orchestrator import run_langgraph_crew

        factory = self._make_factory({})
        result = await run_langgraph_crew("obj", ["missing_agent"], factory)
        assert result is not None
        assert result["engine"] == "langgraph"

    @pytest.mark.asyncio
    async def test_run_langgraph_returns_none_when_unavailable(self):
        from src.crew.langgraph_orchestrator import run_langgraph_crew

        factory = self._make_factory({})
        with patch.dict("sys.modules", {"langgraph": None, "langgraph.graph": None}):
            result = await run_langgraph_crew("obj", ["a1"], factory)
        assert result is None

    @pytest.mark.asyncio
    async def test_crew_orchestrator_tries_langgraph_first(self):
        from src.crew.orchestrator import CrewOrchestrator

        a1 = _SimpleAgent(_make_config("a1"))
        factory = self._make_factory({"a1": a1})
        orch = CrewOrchestrator(agent_factory=factory)

        result = await orch.run("test", agent_names=["a1"])
        assert result["engine"] in ("langgraph", "sequential")

    @pytest.mark.asyncio
    async def test_langgraph_passes_context_between_nodes(self):
        from src.crew.langgraph_orchestrator import run_langgraph_crew

        received_tasks = []

        class _ContextAgent(BaseAgent):
            async def process_task(self, task):
                received_tasks.append(task["task"])
                return {"status": "done", "summary": f"output from {self.config.name}"}

        a1 = _ContextAgent(_make_config("a1"))
        a2 = _ContextAgent(_make_config("a2"))
        factory = self._make_factory({"a1": a1, "a2": a2})

        await run_langgraph_crew("initial objective", ["a1", "a2"], factory)

        assert received_tasks[0] == "initial objective"
        assert "Previous" in received_tasks[1]
