"""Agent factory — creates agent instances from configuration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from src.agents.analysis_agent import AnalysisAgent
from src.agents.base_agent import AgentConfig, AgentType, BaseAgent
from src.agents.kally_agent import KallyAgent
from src.agents.planning_agent import PlanningAgent
from src.agents.research_agent import ResearchAgent
from src.agents.review_agent import ReviewAgent
from src.agents.writing_agent import WritingAgent
from src.cde.cde_agent import CDEAgent
from src.ide.ide_agent import IDEAgent

logger = logging.getLogger(__name__)

_AGENT_CLASSES = {
    AgentType.PLANNING: PlanningAgent,
    AgentType.RESEARCH: ResearchAgent,
    AgentType.ANALYSIS: AnalysisAgent,
    AgentType.WRITING: WritingAgent,
    AgentType.REVIEW: ReviewAgent,
    AgentType.IDE: IDEAgent,
    AgentType.CDE: CDEAgent,
    AgentType.KALLY: KallyAgent,
}

# Config directory relative to project root
_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "agents"


def create_agent(
    config: AgentConfig,
    execution_agent: Optional[Any] = None,
) -> BaseAgent:
    """Instantiate an agent for the given *config*.

    Parameters
    ----------
    config:
        AgentConfig describing the agent to create.
    execution_agent:
        Optional execution agent to inject for validated execution.
    """
    cls = _AGENT_CLASSES.get(config.agent_type)
    if cls is None:
        raise ValueError(f"No agent class registered for type: {config.agent_type}")
    agent = cls(config=config, execution_agent=execution_agent)
    logger.info("Factory created agent '%s'", config.name)
    return agent


def create_agent_from_yaml(
    agent_name: str,
    execution_agent: Optional[Any] = None,
) -> BaseAgent:
    """Load an AgentConfig from a YAML file and create the agent.

    Parameters
    ----------
    agent_name:
        Filename stem (without .yaml) inside *config/agents/*.
    execution_agent:
        Optional execution agent to inject.
    """
    yaml_path = _CONFIG_DIR / f"{agent_name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Agent config not found: {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as fh:
        raw: Dict[str, Any] = yaml.safe_load(fh) or {}

    agent_type_str = raw.get("type", agent_name.replace("_agent", ""))
    try:
        agent_type = AgentType(agent_type_str)
    except ValueError:
        agent_type = AgentType.PLANNING  # fallback

    config = AgentConfig(
        name=raw.get("name", agent_name),
        agent_type=agent_type,
        description=raw.get("description", ""),
        capabilities=raw.get("capabilities", []),
        memory_size=raw.get("memory", {}).get("short_term_size", 100),
        tools=raw.get("tools", []),
        temperature=raw.get("temperature", 0.7),
    )
    return create_agent(config, execution_agent)


class AgentFactory:
    """Factory class wrapping the module-level helpers."""

    def __init__(self, execution_agent: Optional[Any] = None) -> None:
        self._execution_agent = execution_agent
        self._agents: Dict[str, BaseAgent] = {}

    def create_agent(self, config: AgentConfig) -> BaseAgent:
        agent = create_agent(config, self._execution_agent)
        self._agents[config.name] = agent
        return agent

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    def list_agents(self) -> Dict[str, BaseAgent]:
        return dict(self._agents)
