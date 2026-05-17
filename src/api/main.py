"""FastAPI application entry point with lifespan management."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import AgentConfig, AgentType
from src.agents.kally_agent import KallyAgent
from src.llm.provider import LLMProvider, create_llm
from src.api.endpoints import agents, health, tasks
from src.api.endpoints.cde import router as cde_router
from src.api.endpoints.crew import router as crew_router
from src.api.endpoints.ide import router as ide_router
from src.api.endpoints.platform import router as platform_router
from src.api.middleware.auth import APIKeyMiddleware
from src.cde.cde_agent import CDEAgent
from src.execution.execution_agent import ExecutionAgent
from src.execution.execution_engine import ExecutionEngine
from src.ide.ide_agent import IDEAgent
from src.platform.developer_portal import DeveloperPortal
from src.platform.tool_landscape import ToolLandscape

logger = logging.getLogger(__name__)


def _init_llm() -> object:
    """Create an LLM instance from environment variables; returns None in mock mode."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    try:
        llm_provider = LLMProvider(provider)
    except ValueError:
        llm_provider = LLMProvider.OPENAI
    llm = create_llm(
        provider=llm_provider,
        temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.7")),
    )
    if llm is None:
        logger.warning("No LLM API key found — running in mock/fallback mode")
    else:
        logger.info("LLM initialised with provider=%s", provider)
    return llm


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise and tear down application-level resources."""
    logger.info("AGI System starting up...")

    # Initialise LLM
    llm = _init_llm()
    app.state.llm = llm

    # Initialise execution engine and agent
    execution_engine = ExecutionEngine()
    execution_agent = ExecutionAgent(execution_engine=execution_engine)
    app.state.execution_engine = execution_engine
    app.state.execution_agent = execution_agent

    # Initialise agent factory and default agents
    factory = AgentFactory(execution_agent=execution_agent, llm=llm)
    _register_default_agents(factory, execution_agent, llm)
    app.state.agent_factory = factory

    # Initialise crew orchestrator
    from src.crew.orchestrator import CrewOrchestrator
    app.state.crew_orchestrator = CrewOrchestrator(agent_factory=factory, llm=llm)

    # Vibecoding IDE
    ide_config = AgentConfig(
        name="ide_agent",
        agent_type=AgentType.IDE,
        description="AI-powered coding assistant for the vibecoding IDE",
        capabilities=["code_completion", "code_explanation", "refactoring", "bug_fixing"],
    )
    app.state.ide_agent = IDEAgent(config=ide_config, execution_agent=execution_agent)

    # Cloud Development Environment
    cde_config = AgentConfig(
        name="cde_agent",
        agent_type=AgentType.CDE,
        description="Cloud development environment lifecycle manager",
        capabilities=["env_provisioning", "env_management"],
    )
    app.state.cde_agent = CDEAgent(config=cde_config, execution_agent=execution_agent)

    # Platform tooling landscape
    app.state.tool_landscape = ToolLandscape(load_defaults=True)

    # Internal/External developer portal
    app.state.developer_portal = DeveloperPortal(load_defaults=True)

    # Kally AI closed-loop agent
    kally_config = AgentConfig(
        name="kally_agent",
        agent_type=AgentType.KALLY,
        description="Kally AI — closed-loop feedback and continuous improvement",
        capabilities=["signal_ingestion", "anomaly_detection", "auto_correction"],
    )
    app.state.kally_agent = KallyAgent(config=kally_config, execution_agent=execution_agent)

    # Wire the agent factory into the planning agent for delegation
    planning_agent = factory.get_agent("planning_agent")
    if planning_agent is not None:
        planning_agent.set_agent_factory(factory)

    logger.info(
        "AGI System initialised with %d agents + IDE + CDE + Kally AI + Platform",
        len(factory.list_agents()),
    )
    yield

    logger.info("AGI System shutting down...")


def _register_default_agents(
    factory: AgentFactory, execution_agent: ExecutionAgent, llm: object = None
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
        AgentConfig(
            name="coding_agent",
            agent_type=AgentType.CODING,
            description="Code generation, review, and explanation",
            capabilities=["code_generation", "code_review", "code_explanation"],
        ),
        AgentConfig(
            name="summarization_agent",
            agent_type=AgentType.SUMMARIZATION,
            description="Text summarization in multiple styles",
            capabilities=["summarization", "key_point_extraction"],
        ),
    ]
    for config in default_configs:
        factory.create_agent(config)


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
    app.include_router(crew_router)
    app.include_router(ide_router)
    app.include_router(cde_router)
    app.include_router(platform_router)

    # Static dashboard — served at / and /static
    _static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(os.path.join(_static_dir, "index.html"))

    return app


app = create_app()
