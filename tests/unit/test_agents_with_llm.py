"""Unit tests for all agents with a mocked LLM."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.analysis_agent import AnalysisAgent
from src.agents.base_agent import AgentConfig, AgentType
from src.agents.coding_agent import CodingAgent
from src.agents.planning_agent import PlanningAgent
from src.agents.research_agent import ResearchAgent
from src.agents.review_agent import ReviewAgent
from src.agents.summarization_agent import SummarizationAgent
from src.agents.writing_agent import WritingAgent


def _mock_llm(response_content: str) -> MagicMock:
    """Return a mock LLM whose ainvoke() resolves to *response_content*."""
    mock_response = MagicMock()
    mock_response.content = response_content
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    return mock_llm


def _config(agent_type: AgentType, name: str = "test") -> AgentConfig:
    return AgentConfig(name=name, agent_type=agent_type, description="", capabilities=[])


# ── PlanningAgent ─────────────────────────────────────────────────────────────

class TestPlanningAgentWithLlm:
    @pytest.mark.asyncio
    async def test_llm_decompose_used_when_available(self):
        steps = [
            {"step_id": "step_1", "action": "research", "description": "Do something", "agent_type": "research"},
        ]
        llm = _mock_llm(json.dumps(steps))
        agent = PlanningAgent(config=_config(AgentType.PLANNING), llm=llm)
        result = await agent.process_task({"task": "Build an app"})
        assert result["status"] == "completed"
        assert len(result["plan"]["steps"]) == 1

    @pytest.mark.asyncio
    async def test_falls_back_on_invalid_json(self):
        llm = _mock_llm("not json at all")
        agent = PlanningAgent(config=_config(AgentType.PLANNING), llm=llm)
        result = await agent.process_task({"task": "Build an app"})
        assert result["status"] == "completed"
        assert len(result["plan"]["steps"]) > 0


# ── ResearchAgent ─────────────────────────────────────────────────────────────

class TestResearchAgentWithLlm:
    @pytest.mark.asyncio
    async def test_llm_summary_included_in_result(self):
        llm = _mock_llm("Here is a great research summary.")
        agent = ResearchAgent(config=_config(AgentType.RESEARCH), llm=llm)
        result = await agent.process_task({"task": "quantum computing"})
        assert result["status"] == "completed"
        assert "summary" in result


# ── AnalysisAgent ─────────────────────────────────────────────────────────────

class TestAnalysisAgentWithLlm:
    @pytest.mark.asyncio
    async def test_llm_analysis_parsed(self):
        payload = {
            "insights": ["trend upward"],
            "patterns": ["seasonal"],
            "statistics": {"mean": 42},
            "recommendations": ["invest more"],
            "confidence": 0.9,
        }
        llm = _mock_llm(json.dumps(payload))
        agent = AnalysisAgent(config=_config(AgentType.ANALYSIS), llm=llm)
        result = await agent.process_task({"data": {"x": 1}, "analysis_type": "general"})
        assert result["confidence"] == 0.9
        assert result["insights"] == ["trend upward"]

    @pytest.mark.asyncio
    async def test_falls_back_on_bad_json(self):
        llm = _mock_llm("garbage")
        agent = AnalysisAgent(config=_config(AgentType.ANALYSIS), llm=llm)
        result = await agent.process_task({"data": {"a": 1}, "analysis_type": "statistical"})
        assert result["status"] == "completed"


# ── WritingAgent ──────────────────────────────────────────────────────────────

class TestWritingAgentWithLlm:
    @pytest.mark.asyncio
    async def test_llm_outline_used(self):
        call_count = 0

        async def _fake_ainvoke(messages):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if call_count == 1:
                mock_resp.content = json.dumps(["Intro", "Body", "Conclusion"])
            else:
                mock_resp.content = "Section content here."
            return mock_resp

        mock_llm = MagicMock()
        mock_llm.ainvoke = _fake_ainvoke

        agent = WritingAgent(config=_config(AgentType.WRITING), llm=mock_llm)
        result = await agent.process_task({"topic": "AI", "requirements": {}})
        assert "Intro" in result["outline"] or result["word_count"] > 0

    @pytest.mark.asyncio
    async def test_stream_task_yields_chunks(self):
        chunk = MagicMock()
        chunk.content = "streamed content"

        async def _fake_astream(messages):
            yield chunk

        mock_llm = MagicMock()
        mock_llm.astream = _fake_astream

        agent = WritingAgent(config=_config(AgentType.WRITING), llm=mock_llm)
        chunks = []
        async for c in agent.stream_task({"topic": "AI", "requirements": {}}):
            chunks.append(c)
        assert "streamed content" in chunks


# ── ReviewAgent ───────────────────────────────────────────────────────────────

class TestReviewAgentWithLlm:
    @pytest.mark.asyncio
    async def test_llm_review_parsed(self):
        payload = {
            "is_approved": True,
            "score": 0.95,
            "issues": [],
            "suggestions": ["Nice work"],
            "reflection_notes": ["Thorough content"],
        }
        llm = _mock_llm(json.dumps(payload))
        agent = ReviewAgent(config=_config(AgentType.REVIEW), llm=llm)
        result = await agent.process_task({"content": "Great content here", "criteria": {}})
        assert result["is_approved"] is True
        assert result["score"] == 0.95

    @pytest.mark.asyncio
    async def test_falls_back_on_non_json(self):
        llm = _mock_llm("This looks fine to me.")
        agent = ReviewAgent(config=_config(AgentType.REVIEW), llm=llm)
        result = await agent.process_task({"content": "some content", "criteria": {}})
        assert result["status"] == "completed"


# ── CodingAgent ───────────────────────────────────────────────────────────────

class TestCodingAgentWithLlm:
    @pytest.mark.asyncio
    async def test_generate_code_parsed(self):
        payload = {
            "code": "def sort_list(lst): return sorted(lst)",
            "explanation": "Uses Python's built-in sorted().",
            "tests": "assert sort_list([3,1,2]) == [1,2,3]",
        }
        llm = _mock_llm(json.dumps(payload))
        agent = CodingAgent(config=_config(AgentType.CODING), llm=llm)
        result = await agent.generate_code("sort a list")
        assert "sorted" in result.code
        assert result.explanation != ""

    @pytest.mark.asyncio
    async def test_review_code_parsed(self):
        payload = {
            "issues": ["Missing type hints"],
            "suggestions": ["Add return type annotation"],
            "explanation": "Code is functional but lacks annotations.",
        }
        llm = _mock_llm(json.dumps(payload))
        agent = CodingAgent(config=_config(AgentType.CODING), llm=llm)
        result = await agent.review_code("def foo(): return 1")
        assert "Missing type hints" in result.issues

    @pytest.mark.asyncio
    async def test_stream_task_yields_chunks(self):
        chunk = MagicMock()
        chunk.content = "def solution(): pass"

        async def _fake_astream(messages):
            yield chunk

        mock_llm = MagicMock()
        mock_llm.astream = _fake_astream

        agent = CodingAgent(config=_config(AgentType.CODING), llm=mock_llm)
        chunks = []
        async for c in agent.stream_task({"task": "write a function", "language": "python"}):
            chunks.append(c)
        assert "def solution(): pass" in chunks


# ── SummarizationAgent ────────────────────────────────────────────────────────

class TestSummarizationAgentWithLlm:
    @pytest.mark.asyncio
    async def test_summarize_parsed_from_llm(self):
        payload = {
            "summary": "AI is transforming the world.",
            "key_points": ["AI is fast", "AI is powerful"],
        }
        llm = _mock_llm(json.dumps(payload))
        agent = SummarizationAgent(config=_config(AgentType.SUMMARIZATION), llm=llm)
        result = await agent.summarize("Long text about AI " * 20, style="concise")
        assert result.summary == "AI is transforming the world."
        assert len(result.key_points) == 2

    @pytest.mark.asyncio
    async def test_falls_back_on_non_json(self):
        llm = _mock_llm("This is a plain text summary.")
        agent = SummarizationAgent(config=_config(AgentType.SUMMARIZATION), llm=llm)
        result = await agent.summarize("Some content " * 10, style="concise")
        assert "plain text summary" in result.summary

    @pytest.mark.asyncio
    async def test_compression_ratio_computed_from_llm_summary(self):
        payload = {"summary": "Short.", "key_points": []}
        llm = _mock_llm(json.dumps(payload))
        agent = SummarizationAgent(config=_config(AgentType.SUMMARIZATION), llm=llm)
        result = await agent.summarize("word " * 100, style="concise")
        assert result.compression_ratio > 0
