"""LangChain integration — LLM providers, prompt templates, and agent chains.

This module bridges the AGI system's agent layer with LangChain's chain
and prompt abstractions.  All external imports are guarded so the system
degrades gracefully when LangChain dependencies are not installed or LLM
credentials are not configured.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates per agent role
# ---------------------------------------------------------------------------

_ROLE_PROMPTS: Dict[str, Dict[str, str]] = {
    "planning": {
        "system": (
            "You are an expert planning agent.  Your job is to decompose complex "
            "objectives into clear, ordered, executable steps.  Be concise and precise."
        ),
        "human": "Objective: {objective}\n\nDecompose this into a step-by-step plan.",
    },
    "research": {
        "system": (
            "You are an expert research agent.  Gather relevant information from "
            "multiple perspectives, evaluate source quality, and summarise findings."
        ),
        "human": "Research query: {query}\n\nProvide a comprehensive research summary.",
    },
    "analysis": {
        "system": (
            "You are an expert data analysis agent.  Identify patterns, extract "
            "insights, and provide statistical commentary on the data provided."
        ),
        "human": "Data to analyse:\n{data}\n\nAnalysis type: {analysis_type}",
    },
    "writing": {
        "system": (
            "You are an expert writing agent.  Create clear, well-structured content "
            "tailored to the specified audience and tone."
        ),
        "human": "Topic: {topic}\nTone: {tone}\nAudience: {audience}\n\nCreate content.",
    },
    "review": {
        "system": (
            "You are an expert quality assurance agent.  Fact-check content, identify "
            "issues, and suggest concrete improvements."
        ),
        "human": "Content to review:\n{content}\n\nCriteria:\n{criteria}",
    },
}


# ---------------------------------------------------------------------------
# LLM provider
# ---------------------------------------------------------------------------


class LangChainLLMProvider:
    """Wraps a LangChain-compatible LLM with automatic provider selection.

    Priority order: OpenAI → Anthropic → mock fallback.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._llm: Optional[Any] = None
        self._mock_mode = False
        self._init_llm()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_llm(self) -> None:
        """Attempt to instantiate a real LLM, fall back to mock."""
        if os.getenv("OPENAI_API_KEY"):
            self._llm = self._try_openai()
        if self._llm is None and os.getenv("ANTHROPIC_API_KEY"):
            self._llm = self._try_anthropic()
        if self._llm is None:
            logger.warning(
                "No LLM credentials found; LangChainLLMProvider running in mock mode"
            )
            self._mock_mode = True

    def _try_openai(self) -> Optional[Any]:
        try:
            from langchain_community.chat_models import ChatOpenAI  # type: ignore[import]

            model = self._model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            llm = ChatOpenAI(model=model, temperature=self._temperature)
            logger.info("LangChainLLMProvider: using OpenAI (%s)", model)
            return llm
        except Exception as exc:  # noqa: BLE001
            logger.debug("OpenAI init failed: %s", exc)
            return None

    def _try_anthropic(self) -> Optional[Any]:
        try:
            from langchain_community.chat_models import ChatAnthropic  # type: ignore[import]

            model = self._model or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            llm = ChatAnthropic(model=model, temperature=self._temperature)
            logger.info("LangChainLLMProvider: using Anthropic (%s)", model)
            return llm
        except Exception as exc:  # noqa: BLE001
            logger.debug("Anthropic init failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """Invoke the LLM with *messages* and return the text response."""
        if self._mock_mode or self._llm is None:
            return self._mock_response(messages)
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # type: ignore[import]

            lc_messages = []
            for msg in messages:
                role = msg.get("role", "human")
                content = msg.get("content", "")
                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))
            response = self._llm.invoke(lc_messages)
            return str(response.content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM invocation failed, returning mock: %s", exc)
            return self._mock_response(messages)

    @staticmethod
    def _mock_response(messages: List[Dict[str, str]]) -> str:
        last_human = next(
            (m["content"] for m in reversed(messages) if m.get("role") != "system"),
            "No input",
        )
        return f"[Mock LLM response for: {last_human[:80]}]"

    @property
    def is_mock(self) -> bool:
        return self._mock_mode


# ---------------------------------------------------------------------------
# Prompt template builder
# ---------------------------------------------------------------------------


@dataclass
class RenderedPrompt:
    """A fully rendered prompt ready for LLM invocation."""

    messages: List[Dict[str, str]] = field(default_factory=list)


class AgentPromptBuilder:
    """Builds role-specific prompts for AGI system agents."""

    def build(self, role: str, variables: Dict[str, Any]) -> RenderedPrompt:
        """Return a rendered prompt for *role* with *variables* substituted."""
        templates = _ROLE_PROMPTS.get(role, _ROLE_PROMPTS["planning"])
        messages: List[Dict[str, str]] = []

        system_tpl = templates.get("system", "")
        if system_tpl:
            messages.append({"role": "system", "content": system_tpl})

        human_tpl = templates.get("human", "{input}")
        try:
            human_content = human_tpl.format_map(variables)
        except KeyError:
            human_content = human_tpl
        messages.append({"role": "human", "content": human_content})

        return RenderedPrompt(messages=messages)


# ---------------------------------------------------------------------------
# Agent chain
# ---------------------------------------------------------------------------


class LangChainAgentChain:
    """Thin chain wrapper that combines a prompt builder with an LLM provider.

    Usage::

        chain = LangChainAgentChain(role="research", temperature=0.5)
        result = chain.run(query="AI news", ...)
    """

    def __init__(
        self,
        role: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        llm_provider: Optional[LangChainLLMProvider] = None,
    ) -> None:
        self._role = role
        self._prompt_builder = AgentPromptBuilder()
        self._provider = llm_provider or LangChainLLMProvider(
            model=model, temperature=temperature
        )

    def run(self, **variables: Any) -> str:
        """Render the prompt for *variables* and invoke the LLM."""
        prompt = self._prompt_builder.build(self._role, variables)
        return self._provider.invoke(prompt.messages)

    @property
    def is_mock(self) -> bool:
        return self._provider.is_mock


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def create_langchain_chain(
    role: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    llm_provider: Optional[LangChainLLMProvider] = None,
) -> LangChainAgentChain:
    """Create a :class:`LangChainAgentChain` for the given *role*."""
    return LangChainAgentChain(
        role=role,
        model=model,
        temperature=temperature,
        llm_provider=llm_provider,
    )
