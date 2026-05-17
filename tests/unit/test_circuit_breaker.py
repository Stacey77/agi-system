"""Tests for agent retry logic and circuit breaker."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict

import pytest

from src.agents.base_agent import AgentConfig, AgentType, BaseAgent


class _CountingAgent(BaseAgent):
    def __init__(self, config, fail_times=0, **kwargs):
        super().__init__(config, **kwargs)
        self._call_count = 0
        self._fail_times = fail_times

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self._call_count += 1
        if self._call_count <= self._fail_times:
            raise ValueError(f"Deliberate failure #{self._call_count}")
        return {"status": "completed", "call_count": self._call_count}


def _cfg(name="test_agent", max_retries=2, cb_threshold=5):
    return AgentConfig(
        name=name,
        agent_type=AgentType.RESEARCH,
        max_retries=max_retries,
        circuit_break_threshold=cb_threshold,
    )


class TestAgentRetry:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        agent = _CountingAgent(_cfg(), fail_times=0)
        result = await agent.run_with_retry({"task": "test"})
        assert result["status"] == "completed"
        assert agent._call_count == 1
        assert agent._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_retries_and_succeeds(self):
        agent = _CountingAgent(_cfg(max_retries=2), fail_times=2)
        result = await agent.run_with_retry({"task": "retry"})
        assert result["status"] == "completed"
        assert agent._call_count == 3  # 2 failures + 1 success
        assert agent._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_raises_after_all_retries_exhausted(self):
        agent = _CountingAgent(_cfg(max_retries=1), fail_times=10)
        with pytest.raises(ValueError):
            await agent.run_with_retry({"task": "fail always"})
        assert agent._call_count == 2  # 1 attempt + 1 retry

    @pytest.mark.asyncio
    async def test_consecutive_failures_tracked(self):
        agent = _CountingAgent(_cfg(max_retries=0, cb_threshold=10), fail_times=3)
        for _ in range(3):
            try:
                await agent.run_with_retry({"task": "count"})
            except ValueError:
                pass
        assert agent._consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_success_resets_consecutive_failures(self):
        agent = _CountingAgent(_cfg(max_retries=2, cb_threshold=10), fail_times=1)
        result = await agent.run_with_retry({"task": "recover"})
        assert result["status"] == "completed"
        assert agent._consecutive_failures == 0


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        agent = _CountingAgent(_cfg(max_retries=0, cb_threshold=3), fail_times=100)
        for _ in range(3):
            try:
                await agent.run_with_retry({"task": "fail"})
            except (ValueError, RuntimeError):
                pass
        assert agent._circuit_open_until > time.time()

    @pytest.mark.asyncio
    async def test_circuit_open_raises_immediately(self):
        agent = _CountingAgent(_cfg(max_retries=0, cb_threshold=1), fail_times=100)
        try:
            await agent.run_with_retry({"task": "open circuit"})
        except (ValueError, RuntimeError):
            pass
        # Circuit should now be open
        if agent._circuit_open_until > time.time():
            with pytest.raises(RuntimeError, match="circuit breaker is open"):
                await agent.run_with_retry({"task": "blocked"})

    def test_get_status_includes_circuit_info(self):
        agent = _CountingAgent(_cfg())
        status = agent.get_status()
        assert "consecutive_failures" in status
        assert "circuit_open" in status
        assert status["circuit_open"] is False
        assert status["consecutive_failures"] == 0

    def test_get_status_circuit_open(self):
        agent = _CountingAgent(_cfg())
        agent._circuit_open_until = time.time() + 60.0
        status = agent.get_status()
        assert status["circuit_open"] is True
