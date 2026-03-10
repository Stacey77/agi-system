"""Unit tests for agent creation, task processing, and factory pattern."""

from __future__ import annotations

import pytest

from src.agents.agent_factory import AgentFactory, create_agent
from src.agents.analysis_agent import AnalysisAgent
from src.agents.base_agent import AgentConfig, AgentMemory, AgentType
from src.agents.planning_agent import PlanningAgent
from src.agents.research_agent import ResearchAgent
from src.agents.review_agent import ReviewAgent
from src.agents.writing_agent import WritingAgent


# ---------------------------------------------------------------------------
# AgentMemory
# ---------------------------------------------------------------------------

class TestAgentMemory:
    def test_add_and_get(self):
        mem = AgentMemory(max_size=3)
        mem.add({"k": "v1"})
        mem.add({"k": "v2"})
        assert len(mem) == 2
        assert mem.get_all()[0] == {"k": "v1"}

    def test_eviction(self):
        mem = AgentMemory(max_size=2)
        mem.add({"n": 1})
        mem.add({"n": 2})
        mem.add({"n": 3})
        assert len(mem) == 2
        assert mem.get_all()[0]["n"] == 2

    def test_clear(self):
        mem = AgentMemory(max_size=5)
        mem.add({"x": 1})
        mem.clear()
        assert len(mem) == 0


# ---------------------------------------------------------------------------
# create_agent factory function
# ---------------------------------------------------------------------------

class TestCreateAgent:
    def test_creates_planning_agent(self):
        config = AgentConfig(
            name="planner",
            agent_type=AgentType.PLANNING,
        )
        agent = create_agent(config)
        assert isinstance(agent, PlanningAgent)

    def test_creates_research_agent(self):
        config = AgentConfig(name="res", agent_type=AgentType.RESEARCH)
        agent = create_agent(config)
        assert isinstance(agent, ResearchAgent)

    def test_creates_analysis_agent(self):
        config = AgentConfig(name="ana", agent_type=AgentType.ANALYSIS)
        agent = create_agent(config)
        assert isinstance(agent, AnalysisAgent)

    def test_creates_writing_agent(self):
        config = AgentConfig(name="wri", agent_type=AgentType.WRITING)
        agent = create_agent(config)
        assert isinstance(agent, WritingAgent)

    def test_creates_review_agent(self):
        config = AgentConfig(name="rev", agent_type=AgentType.REVIEW)
        agent = create_agent(config)
        assert isinstance(agent, ReviewAgent)

    def test_unsupported_type_raises(self):
        config = AgentConfig(name="exe", agent_type=AgentType.EXECUTION)
        with pytest.raises(ValueError):
            create_agent(config)


# ---------------------------------------------------------------------------
# AgentFactory class
# ---------------------------------------------------------------------------

class TestAgentFactory:
    def test_create_and_retrieve(self):
        factory = AgentFactory()
        config = AgentConfig(name="my_agent", agent_type=AgentType.WRITING)
        factory.create_agent(config)
        assert factory.get_agent("my_agent") is not None

    def test_list_agents(self):
        factory = AgentFactory()
        for name, atype in [("a1", AgentType.PLANNING), ("a2", AgentType.RESEARCH)]:
            factory.create_agent(AgentConfig(name=name, agent_type=atype))
        assert len(factory.list_agents()) == 2


# ---------------------------------------------------------------------------
# PlanningAgent
# ---------------------------------------------------------------------------

class TestPlanningAgent:
    @pytest.mark.asyncio
    async def test_process_task_returns_plan(self):
        config = AgentConfig(name="planner", agent_type=AgentType.PLANNING)
        agent = PlanningAgent(config)
        result = await agent.process_task({"objective": "Write a report on AI"})
        assert result["status"] == "completed"
        assert "plan" in result
        assert "steps" in result["plan"]

    @pytest.mark.asyncio
    async def test_create_executable_plan(self):
        config = AgentConfig(name="planner", agent_type=AgentType.PLANNING)
        agent = PlanningAgent(config)
        plan = await agent.create_executable_plan("Analyse market trends")
        assert plan.objective == "Analyse market trends"
        assert len(plan.steps) > 0
        assert isinstance(plan.dependencies, dict)

    def test_get_status(self):
        config = AgentConfig(name="planner", agent_type=AgentType.PLANNING)
        agent = PlanningAgent(config)
        status = agent.get_status()
        assert status["name"] == "planner"
        assert status["type"] == AgentType.PLANNING


# ---------------------------------------------------------------------------
# ResearchAgent
# ---------------------------------------------------------------------------

class TestResearchAgent:
    @pytest.mark.asyncio
    async def test_conduct_research(self):
        config = AgentConfig(name="res", agent_type=AgentType.RESEARCH, tools=[])
        agent = ResearchAgent(config)
        result = await agent.conduct_research("quantum computing")
        assert result.query == "quantum computing"
        assert isinstance(result.sources, list)
        assert isinstance(result.quality_score, float)

    @pytest.mark.asyncio
    async def test_process_task(self):
        config = AgentConfig(name="res", agent_type=AgentType.RESEARCH)
        agent = ResearchAgent(config)
        result = await agent.process_task({"query": "test query"})
        assert result["status"] == "completed"
        assert "sources" in result


# ---------------------------------------------------------------------------
# AnalysisAgent
# ---------------------------------------------------------------------------

class TestAnalysisAgent:
    @pytest.mark.asyncio
    async def test_statistical_analysis(self):
        config = AgentConfig(name="ana", agent_type=AgentType.ANALYSIS)
        agent = AnalysisAgent(config)
        data = {"a": 1, "b": 2, "c": 3}
        result = await agent.analyze_data(data, "statistical")
        assert result.analysis_type == "statistical"
        assert "mean" in result.statistics

    @pytest.mark.asyncio
    async def test_general_analysis(self):
        config = AgentConfig(name="ana", agent_type=AgentType.ANALYSIS)
        agent = AnalysisAgent(config)
        result = await agent.analyze_data({"x": "y"}, "general")
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_sentiment_analysis(self):
        config = AgentConfig(name="ana", agent_type=AgentType.ANALYSIS)
        agent = AnalysisAgent(config)
        result = await agent.analyze_data({"text": "This is great and excellent"}, "sentiment")
        assert len(result.insights) > 0


# ---------------------------------------------------------------------------
# WritingAgent
# ---------------------------------------------------------------------------

class TestWritingAgent:
    @pytest.mark.asyncio
    async def test_create_document(self):
        config = AgentConfig(name="wri", agent_type=AgentType.WRITING)
        agent = WritingAgent(config)
        doc = await agent.create_document("AI Ethics", {"tone": "academic"})
        assert "AI Ethics" in doc.title
        assert len(doc.outline) > 0
        assert doc.word_count > 0

    @pytest.mark.asyncio
    async def test_process_task(self):
        config = AgentConfig(name="wri", agent_type=AgentType.WRITING)
        agent = WritingAgent(config)
        result = await agent.process_task({"topic": "Machine Learning", "requirements": {}})
        assert result["status"] == "completed"
        assert "content" in result


# ---------------------------------------------------------------------------
# ReviewAgent
# ---------------------------------------------------------------------------

class TestReviewAgent:
    @pytest.mark.asyncio
    async def test_approve_good_content(self):
        config = AgentConfig(name="rev", agent_type=AgentType.REVIEW)
        agent = ReviewAgent(config)
        review = await agent.review_output("This is a sufficiently long content.", {})
        assert review.score > 0

    @pytest.mark.asyncio
    async def test_flag_empty_content(self):
        config = AgentConfig(name="rev", agent_type=AgentType.REVIEW)
        agent = ReviewAgent(config)
        review = await agent.review_output("", {})
        assert not review.is_approved
        assert len(review.issues) > 0

    @pytest.mark.asyncio
    async def test_self_correction_applied(self):
        config = AgentConfig(name="rev", agent_type=AgentType.REVIEW)
        agent = ReviewAgent(config)
        review = await agent.review_output("Short.", {"min_length": 100})
        assert review.corrected_content is not None
