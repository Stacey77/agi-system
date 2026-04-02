"""FastAPI application entry point with lifespan management."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import AgentConfig, AgentType
from src.api.endpoints import agents, crews, health, tasks
from src.api.middleware.auth import APIKeyMiddleware
from src.execution.execution_agent import ExecutionAgent
from src.execution.execution_engine import ExecutionEngine
from src.tools.calculator_tool import CalculatorTool
from src.tools.database_tool import DatabaseTool
from src.tools.document_parser_tool import DocumentParserTool
from src.tools.tool_registry import ToolRegistry
from src.tools.web_search_tool import WebSearchTool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise and tear down application-level resources."""
    logger.info("AGI System starting up...")

    # Initialise tool registry
    tool_registry = _build_tool_registry()
    app.state.tool_registry = tool_registry

    # Initialise execution engine and agent
    execution_engine = ExecutionEngine()
    execution_agent = ExecutionAgent(execution_engine=execution_engine)
    app.state.execution_engine = execution_engine
    app.state.execution_agent = execution_agent

    # Initialise agent factory and default agents
    factory = AgentFactory(execution_agent=execution_agent)
    _register_default_agents(factory, execution_agent, tool_registry)
    app.state.agent_factory = factory

    logger.info("AGI System initialised with %d agents", len(factory.list_agents()))
    yield

    logger.info("AGI System shutting down...")


def _build_tool_registry() -> ToolRegistry:
    """Instantiate and populate the default tool registry."""
    registry = ToolRegistry()
    registry.register_tool(WebSearchTool())
    registry.register_tool(CalculatorTool())
    registry.register_tool(DocumentParserTool())
    registry.register_tool(DatabaseTool())
    logger.info("ToolRegistry populated with %d tools", len(registry))
    return registry


def _register_default_agents(
    factory: AgentFactory,
    execution_agent: ExecutionAgent,
    tool_registry: ToolRegistry,
) -> None:
    default_configs = [
        AgentConfig(
            name="planning_agent",
            agent_type=AgentType.PLANNING,
            description="Decomposes objectives into executable plans",
            capabilities=["task_decomposition", "dependency_analysis"],
        ),
        AgentConfig(
            name="research_agent",
            agent_type=AgentType.RESEARCH,
            description="Multi-source information gathering",
            capabilities=["web_search", "source_assessment"],
            tools=["web_search"],
        ),
        AgentConfig(
            name="analysis_agent",
            agent_type=AgentType.ANALYSIS,
            description="Data processing and insight extraction",
            capabilities=["statistical_analysis", "pattern_recognition"],
            tools=["calculator"],
        ),
        AgentConfig(
            name="writing_agent",
            agent_type=AgentType.WRITING,
            description="Content generation with outline→draft→edit pipeline",
            capabilities=["content_generation", "style_adaptation"],
        ),
        AgentConfig(
            name="review_agent",
            agent_type=AgentType.REVIEW,
            description="Quality assurance and fact-checking",
            capabilities=["quality_assurance", "fact_checking"],
        ),
    ]
    for config in default_configs:
        agent = factory.create_agent(config)
        agent.set_tool_registry(tool_registry)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AGI System API",
        description="AGI-type system for smart chatbots, writing assistants, and research tools",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth
    app.add_middleware(APIKeyMiddleware)

    # Routers
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(tasks.router)
    app.include_router(crews.router)

    return app


app = create_app()
