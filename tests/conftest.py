"""Shared pytest fixtures for the AGI system test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.agents.base_agent import AgentConfig, AgentType
from src.execution.execution_agent import ExecutionAgent
from src.execution.execution_engine import ExecutionEngine


@pytest.fixture
def mock_execution_engine() -> ExecutionEngine:
    """Provide a fresh ExecutionEngine instance."""
    return ExecutionEngine(max_concurrency=2)


@pytest.fixture
def execution_agent(mock_execution_engine: ExecutionEngine) -> ExecutionAgent:
    """Provide a fresh ExecutionAgent wired to the mock engine."""
    return ExecutionAgent(execution_engine=mock_execution_engine)


@pytest.fixture
def sample_agent_config() -> AgentConfig:
    """Provide a basic AgentConfig for testing."""
    return AgentConfig(
        name="test_agent",
        agent_type=AgentType.RESEARCH,
        description="A test agent",
        capabilities=["testing"],
        memory_size=10,
        tools=["web_search"],
        temperature=0.5,
    )


@pytest.fixture
def sample_task() -> dict:
    """Provide a minimal valid task dictionary."""
    return {
        "task_id": "test_task_001",
        "action": "research",
        "objective": "Test the AGI system",
    }


@pytest.fixture
def test_client() -> TestClient:
    """Provide a FastAPI TestClient (no auth key configured)."""
    from src.api.main import create_app

    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as client:
        yield client
