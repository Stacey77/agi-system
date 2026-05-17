"""LLM provider factory — wraps OpenAI and Anthropic via LangChain."""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM backend providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


def create_llm(
    provider: str = "openai",
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    api_key: Optional[str] = None,
) -> Optional[object]:
    """Instantiate a LangChain chat model for the given provider.

    Returns ``None`` (graceful no-op) when the required API key is absent or
    the optional LangChain provider package is not installed.
    """
    provider = provider.lower()

    if provider == LLMProvider.OPENAI:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            logger.warning("OPENAI_API_KEY not set — LLM disabled for this agent")
            return None
        try:
            from langchain_openai import ChatOpenAI  # type: ignore

            resolved_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            llm = ChatOpenAI(
                model=resolved_model,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=key,
                streaming=True,
            )
            logger.info("Initialised OpenAI LLM: %s", resolved_model)
            return llm
        except ImportError:
            logger.warning("langchain-openai not installed — run: pip install langchain-openai")
            return None

    if provider == LLMProvider.ANTHROPIC:
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            logger.warning("ANTHROPIC_API_KEY not set — LLM disabled for this agent")
            return None
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore

            resolved_model = model or os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
            llm = ChatAnthropic(
                model=resolved_model,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=key,
            )
            logger.info("Initialised Anthropic LLM: %s", resolved_model)
            return llm
        except ImportError:
            logger.warning(
                "langchain-anthropic not installed — run: pip install langchain-anthropic"
            )
            return None

    logger.warning("Unknown LLM provider '%s' — LLM disabled", provider)
    return None


async def stream_llm_response(llm: object, prompt: str) -> AsyncIterator[str]:
    """Yield text chunks from an LLM using LangChain's async streaming interface."""
    from langchain_core.messages import HumanMessage  # type: ignore

    async for chunk in llm.astream([HumanMessage(content=prompt)]):  # type: ignore[union-attr]
        delta = getattr(chunk, "content", "")
        if delta:
            yield delta


async def invoke_llm(
    llm: object,
    system_prompt: str,
    user_prompt: str,
    agent_name: str = "unknown",
    task_id: Optional[str] = None,
    tracker: Optional[object] = None,
) -> str:
    """Invoke an LLM with a system + user message pair and return the full response.

    If *tracker* is provided, token usage is recorded after each call.
    """
    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    response = await llm.ainvoke(messages)  # type: ignore[union-attr]

    # Capture usage metadata if available and tracker provided
    if tracker is not None:
        usage = getattr(response, "usage_metadata", None) or getattr(response, "response_metadata", {})
        model = getattr(llm, "model_name", getattr(llm, "model", "unknown"))
        input_tokens = (
            getattr(usage, "input_tokens", None)
            or (usage.get("token_usage", {}) if isinstance(usage, dict) else {}).get("prompt_tokens", 0)
        ) or 0
        output_tokens = (
            getattr(usage, "output_tokens", None)
            or (usage.get("token_usage", {}) if isinstance(usage, dict) else {}).get("completion_tokens", 0)
        ) or 0
        try:
            tracker.record(  # type: ignore[attr-defined]
                agent_name=agent_name,
                model=str(model),
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                task_id=task_id,
            )
        except Exception:  # noqa: BLE001
            pass

    return str(getattr(response, "content", response))
