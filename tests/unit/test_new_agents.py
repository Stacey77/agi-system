"""Unit tests for CodingAgent and SummarizationAgent (no LLM required)."""

from __future__ import annotations

import pytest

from src.agents.base_agent import AgentConfig, AgentType
from src.agents.coding_agent import CodeResult, CodingAgent
from src.agents.summarization_agent import SummaryResult, SummarizationAgent


def _coding_agent() -> CodingAgent:
    config = AgentConfig(
        name="test_coding",
        agent_type=AgentType.CODING,
        description="test",
        capabilities=[],
    )
    return CodingAgent(config=config, llm=None)


def _summarization_agent() -> SummarizationAgent:
    config = AgentConfig(
        name="test_summarization",
        agent_type=AgentType.SUMMARIZATION,
        description="test",
        capabilities=[],
    )
    return SummarizationAgent(config=config, llm=None)


# ── CodingAgent ──────────────────────────────────────────────────────────────

class TestCodingAgentFallback:
    @pytest.mark.asyncio
    async def test_generate_returns_stub(self):
        agent = _coding_agent()
        result = await agent.generate_code("sort a list", language="python")
        assert isinstance(result, CodeResult)
        assert "solution" in result.code
        assert result.language == "python"

    @pytest.mark.asyncio
    async def test_review_detects_eval(self):
        agent = _coding_agent()
        result = await agent.review_code("x = eval(input())", "python")
        assert any("eval" in issue for issue in result.issues)

    @pytest.mark.asyncio
    async def test_review_suggests_docstring_when_missing(self):
        agent = _coding_agent()
        result = await agent.review_code("def foo():\n    return 1\n", "python")
        assert any("docstring" in s.lower() or "comment" in s.lower() for s in result.suggestions)

    @pytest.mark.asyncio
    async def test_explain_returns_explanation(self):
        agent = _coding_agent()
        result = await agent.explain_code("def foo(): pass", "python")
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0

    @pytest.mark.asyncio
    async def test_process_task_generate(self):
        agent = _coding_agent()
        result = await agent.process_task({"task": "reverse a string", "mode": "generate", "language": "python"})
        assert result["status"] == "completed"
        assert "code" in result
        assert result["mode"] == "generate"

    @pytest.mark.asyncio
    async def test_process_task_review(self):
        agent = _coding_agent()
        result = await agent.process_task({"mode": "review", "code": "x = 1", "language": "python"})
        assert result["status"] == "completed"
        assert "issues" in result

    @pytest.mark.asyncio
    async def test_process_task_explain(self):
        agent = _coding_agent()
        result = await agent.process_task({"mode": "explain", "code": "print('hi')", "language": "python"})
        assert result["status"] == "completed"
        assert "explanation" in result

    @pytest.mark.asyncio
    async def test_stream_task_yields_json(self):
        agent = _coding_agent()
        chunks = []
        async for chunk in agent.stream_task({"task": "hello world", "language": "python"}):
            chunks.append(chunk)
        assert len(chunks) >= 1
        import json
        data = json.loads(chunks[0])
        assert "status" in data


# ── SummarizationAgent ───────────────────────────────────────────────────────

class TestSummarizationAgentFallback:
    _TEXT = (
        "The quick brown fox jumps over the lazy dog. "
        "Machine learning is transforming every industry. "
        "Large language models are trained on vast corpora. "
        "Natural language processing enables human-computer interaction. "
        "Deep learning architectures power modern AI systems."
    )

    @pytest.mark.asyncio
    async def test_summarize_concise_is_short(self):
        agent = _summarization_agent()
        result = await agent.summarize(self._TEXT, style="concise")
        assert isinstance(result, SummaryResult)
        assert len(result.summary) > 0
        assert result.style == "concise"

    @pytest.mark.asyncio
    async def test_summarize_detailed_has_more_sentences(self):
        agent = _summarization_agent()
        concise = await agent.summarize(self._TEXT, style="concise")
        detailed = await agent.summarize(self._TEXT, style="detailed")
        assert len(detailed.summary) >= len(concise.summary)

    @pytest.mark.asyncio
    async def test_key_points_extracted(self):
        agent = _summarization_agent()
        result = await agent.summarize(self._TEXT, style="bullet")
        assert isinstance(result.key_points, list)
        assert len(result.key_points) > 0

    @pytest.mark.asyncio
    async def test_compression_ratio_is_non_negative(self):
        agent = _summarization_agent()
        result = await agent.summarize(self._TEXT, style="concise")
        assert result.compression_ratio >= 0

    @pytest.mark.asyncio
    async def test_original_length_recorded(self):
        agent = _summarization_agent()
        result = await agent.summarize(self._TEXT, style="concise")
        expected = len(self._TEXT.split())
        assert result.original_length == expected

    @pytest.mark.asyncio
    async def test_empty_text_handled(self):
        agent = _summarization_agent()
        result = await agent.summarize("", style="concise")
        assert isinstance(result, SummaryResult)
        assert result.compression_ratio == 0.0

    @pytest.mark.asyncio
    async def test_process_task_returns_expected_keys(self):
        agent = _summarization_agent()
        result = await agent.process_task({"text": self._TEXT, "style": "concise"})
        assert result["status"] == "completed"
        for key in ("summary", "key_points", "style", "original_length", "compression_ratio"):
            assert key in result
