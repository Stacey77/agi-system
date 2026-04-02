"""Unit tests for the LangChain and CrewAI integration layers."""

from __future__ import annotations

import pytest

from src.agents.base_agent import AgentConfig, AgentType
from src.integrations.crewai_integration import (
    CrewAIAgentBuilder,
    CrewAITaskBuilder,
    CrewBuilder,
    CrewRunResult,
    _MockCrewAIAgent,
    _MockCrewAITask,
)
from src.integrations.langchain_integration import (
    AgentPromptBuilder,
    LangChainAgentChain,
    LangChainLLMProvider,
    RenderedPrompt,
    create_langchain_chain,
)


# ---------------------------------------------------------------------------
# LangChain integration
# ---------------------------------------------------------------------------


class TestLangChainLLMProvider:
    def test_mock_mode_when_no_credentials(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = LangChainLLMProvider()
        assert provider.is_mock is True

    def test_mock_invoke_returns_string(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = LangChainLLMProvider()
        result = provider.invoke([{"role": "human", "content": "Hello"}])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mock_invoke_reflects_input(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = LangChainLLMProvider()
        result = provider.invoke([{"role": "human", "content": "Test query XYZ"}])
        assert "Test query XYZ" in result


class TestAgentPromptBuilder:
    def test_known_role_returns_system_and_human(self):
        builder = AgentPromptBuilder()
        prompt = builder.build("research", {"query": "AI news"})
        assert isinstance(prompt, RenderedPrompt)
        roles = [m["role"] for m in prompt.messages]
        assert "system" in roles
        assert "human" in roles

    def test_human_message_contains_variable(self):
        builder = AgentPromptBuilder()
        prompt = builder.build("research", {"query": "test topic"})
        human_msg = next(m for m in prompt.messages if m["role"] == "human")
        assert "test topic" in human_msg["content"]

    def test_unknown_role_falls_back_gracefully(self):
        builder = AgentPromptBuilder()
        prompt = builder.build("unknown_role", {"objective": "do something"})
        assert len(prompt.messages) > 0

    def test_all_defined_roles(self):
        builder = AgentPromptBuilder()
        for role in ("planning", "research", "analysis", "writing", "review"):
            prompt = builder.build(role, {})
            assert len(prompt.messages) >= 1


class TestLangChainAgentChain:
    def test_run_returns_string(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        chain = create_langchain_chain(role="research")
        result = chain.run(query="Python language")
        assert isinstance(result, str)

    def test_is_mock_without_credentials(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        chain = LangChainAgentChain(role="planning")
        assert chain.is_mock is True

    def test_writing_chain_run(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        chain = create_langchain_chain(role="writing", temperature=0.5)
        result = chain.run(topic="AI", tone="professional", audience="developers")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# CrewAI integration
# ---------------------------------------------------------------------------


class TestCrewAIAgentBuilder:
    def test_builds_mock_agent_without_crewai(self, monkeypatch):
        # Simulate crewai not being importable
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "crewai":
                raise ImportError("crewai not available")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        builder = CrewAIAgentBuilder()
        config = AgentConfig(name="test", agent_type=AgentType.RESEARCH)
        agent = builder.build(config)
        assert isinstance(agent, _MockCrewAIAgent)

    def test_mock_agent_has_role(self):
        config = AgentConfig(name="planner", agent_type=AgentType.PLANNING)
        agent = _MockCrewAIAgent(config)
        assert agent.role == "Planning"

    def test_mock_agent_repr(self):
        config = AgentConfig(name="writer", agent_type=AgentType.WRITING)
        agent = _MockCrewAIAgent(config)
        assert "MockCrewAIAgent" in repr(agent)


class TestCrewAITaskBuilder:
    def test_builds_mock_task_without_crewai(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "crewai":
                raise ImportError("crewai not available")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        builder = CrewAITaskBuilder()
        config = AgentConfig(name="res", agent_type=AgentType.RESEARCH)
        mock_agent = _MockCrewAIAgent(config)
        task = builder.build({"description": "Research AI"}, mock_agent)
        assert isinstance(task, _MockCrewAITask)

    def test_mock_task_description_set(self):
        config = AgentConfig(name="res", agent_type=AgentType.RESEARCH)
        agent = _MockCrewAIAgent(config)
        task = _MockCrewAITask("Analyse data", "Full analysis", agent)
        assert task.description == "Analyse data"
        assert task.expected_output == "Full analysis"


class TestCrewBuilder:
    @pytest.mark.asyncio
    async def test_run_returns_result(self):
        builder = CrewBuilder()
        configs = [
            AgentConfig(name="r", agent_type=AgentType.RESEARCH),
            AgentConfig(name="w", agent_type=AgentType.WRITING),
        ]
        tasks = [{"description": "Research AI trends"}]
        result = await builder.run(agent_configs=configs, tasks=tasks, objective="Test run")
        assert isinstance(result, CrewRunResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_empty_configs_fails(self):
        builder = CrewBuilder()
        result = await builder.run(agent_configs=[], tasks=[], objective="empty")
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_run_multiple_tasks(self):
        builder = CrewBuilder()
        configs = [AgentConfig(name="a", agent_type=AgentType.ANALYSIS)]
        tasks = [
            {"description": "Analyse dataset A"},
            {"description": "Analyse dataset B"},
        ]
        result = await builder.run(agent_configs=configs, tasks=tasks, objective="Multi analysis")
        assert len(result.task_outputs) == 2

    @pytest.mark.asyncio
    async def test_mock_run_flag(self):
        builder = CrewBuilder()
        configs = [AgentConfig(name="p", agent_type=AgentType.PLANNING)]
        result = await builder.run(
            agent_configs=configs,
            tasks=[{"description": "Plan project"}],
            objective="Project planning",
        )
        # Without real CrewAI credentials the result should use mock
        assert isinstance(result.used_mock, bool)
        assert result.output != ""


# ---------------------------------------------------------------------------
# Crew API endpoint tests (via integration test client)
# ---------------------------------------------------------------------------


class TestCrewEndpoints:
    def test_list_crew_agents(self, test_client):
        response = test_client.get("/api/v1/crews/agents")
        assert response.status_code == 200
        agents = response.json()
        assert isinstance(agents, list)
        assert len(agents) > 0

    def test_run_crew_default_agents(self, test_client):
        response = test_client.post(
            "/api/v1/crews/run",
            json={"objective": "Summarise recent AI trends"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "output" in data

    def test_run_crew_specific_agents(self, test_client):
        response = test_client.post(
            "/api/v1/crews/run",
            json={
                "objective": "Research and write about Python",
                "agent_names": ["research_agent", "writing_agent"],
                "tasks": [
                    {"description": "Research Python language"},
                    {"description": "Write a summary about Python"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["objective"] == "Research and write about Python"

    def test_run_crew_unknown_agent(self, test_client):
        response = test_client.post(
            "/api/v1/crews/run",
            json={
                "objective": "Test",
                "agent_names": ["nonexistent_agent"],
            },
        )
        assert response.status_code == 404
