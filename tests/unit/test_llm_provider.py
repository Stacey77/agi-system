"""Unit tests for the LLM provider module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.provider import LLMProvider, create_llm, invoke_llm, stream_llm_response


class TestCreateLlm:
    def test_returns_none_when_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = create_llm(provider=LLMProvider.OPENAI, api_key=None)
        assert result is None

    def test_returns_none_for_anthropic_when_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = create_llm(provider=LLMProvider.ANTHROPIC, api_key=None)
        assert result is None

    def test_returns_llm_when_openai_key_provided(self):
        mock_llm = MagicMock()
        with patch("src.llm.provider.LLMProvider", LLMProvider):
            try:
                from langchain_openai import ChatOpenAI  # noqa: F401
            except ImportError:
                pytest.skip("langchain-openai not installed")
            with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
                result = create_llm(provider=LLMProvider.OPENAI, api_key="test-key")
        assert result is not None

    def test_returns_llm_when_anthropic_key_provided(self):
        mock_llm = MagicMock()
        try:
            from langchain_anthropic import ChatAnthropic  # noqa: F401
        except ImportError:
            pytest.skip("langchain-anthropic not installed")
        with patch("langchain_anthropic.ChatAnthropic", return_value=mock_llm):
            result = create_llm(provider=LLMProvider.ANTHROPIC, api_key="test-key")
        assert result is not None

    def test_env_key_used_when_no_explicit_key(self):
        try:
            from langchain_openai import ChatOpenAI  # noqa: F401
        except ImportError:
            pytest.skip("langchain-openai not installed")
        mock_llm = MagicMock()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
                result = create_llm(provider=LLMProvider.OPENAI)
        assert result is not None


@pytest.mark.asyncio
class TestInvokeLlm:
    async def test_invoke_returns_content_string(self):
        mock_response = MagicMock()
        mock_response.content = "Hello from LLM"
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        result = await invoke_llm(mock_llm, "system prompt", "user prompt")
        assert result == "Hello from LLM"

    async def test_invoke_calls_ainvoke_with_messages(self):
        mock_response = MagicMock()
        mock_response.content = "response"
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        await invoke_llm(mock_llm, "sys", "usr")
        mock_llm.ainvoke.assert_called_once()
        messages = mock_llm.ainvoke.call_args[0][0]
        assert len(messages) == 2

    async def test_invoke_handles_empty_system_prompt(self):
        mock_response = MagicMock()
        mock_response.content = "ok"
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        result = await invoke_llm(mock_llm, "", "user only")
        assert result == "ok"


@pytest.mark.asyncio
class TestStreamLlmResponse:
    async def test_stream_yields_chunks(self):
        chunk1, chunk2 = MagicMock(), MagicMock()
        chunk1.content = "Hello"
        chunk2.content = " world"

        async def _fake_astream(messages):
            for c in [chunk1, chunk2]:
                yield c

        mock_llm = MagicMock()
        mock_llm.astream = _fake_astream

        chunks = []
        async for chunk in stream_llm_response(mock_llm, "test prompt"):
            chunks.append(chunk)

        assert chunks == ["Hello", " world"]

    async def test_stream_skips_empty_chunks(self):
        chunk1, chunk2 = MagicMock(), MagicMock()
        chunk1.content = "data"
        chunk2.content = ""

        async def _fake_astream(messages):
            for c in [chunk1, chunk2]:
                yield c

        mock_llm = MagicMock()
        mock_llm.astream = _fake_astream

        chunks = []
        async for chunk in stream_llm_response(mock_llm, "prompt"):
            chunks.append(chunk)

        assert chunks == ["data"]
