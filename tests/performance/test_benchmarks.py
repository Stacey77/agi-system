"""Performance benchmarks — latency, throughput, and concurrent execution."""

from __future__ import annotations

import asyncio
import time
from typing import List

import pytest

from src.execution.execution_engine import ExecutionEngine


class TestExecutionLatency:
    @pytest.mark.asyncio
    async def test_single_task_latency(self):
        """Single task should complete in under 1 second."""
        engine = ExecutionEngine()
        plan = {"tasks": [{"task_id": "perf_t1", "action": "run"}], "dependencies": {}}
        start = time.monotonic()
        results = await engine.execute_plan(plan)
        elapsed = time.monotonic() - start
        assert len(results) == 1
        assert elapsed < 1.0, f"Single task took {elapsed:.3f}s (expected <1s)"

    @pytest.mark.asyncio
    async def test_batch_task_latency(self):
        """Ten independent tasks should complete in under 3 seconds."""
        engine = ExecutionEngine(max_concurrency=5)
        tasks = [{"task_id": f"perf_{i}", "action": "run"} for i in range(10)]
        plan = {"tasks": tasks, "dependencies": {}}
        start = time.monotonic()
        results = await engine.execute_plan(plan)
        elapsed = time.monotonic() - start
        assert len(results) == 10
        assert elapsed < 3.0, f"Batch of 10 took {elapsed:.3f}s (expected <3s)"


class TestConcurrentExecution:
    @pytest.mark.asyncio
    async def test_concurrent_plans(self):
        """Multiple plans executed concurrently should all succeed."""
        engine = ExecutionEngine(max_concurrency=4)

        async def run_plan(idx: int):
            plan = {
                "tasks": [{"task_id": f"c{idx}_t1", "action": "run"}],
                "dependencies": {},
            }
            return await engine.execute_plan(plan)

        results_list = await asyncio.gather(*[run_plan(i) for i in range(5)])
        for results in results_list:
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Semaphore should not allow more than max_concurrency simultaneous tasks."""
        engine = ExecutionEngine(max_concurrency=2)
        tasks = [{"task_id": f"s{i}", "action": "run"} for i in range(6)]
        plan = {"tasks": tasks, "dependencies": {}}
        results = await engine.execute_plan(plan)
        assert len(results) == 6


class TestThroughput:
    @pytest.mark.asyncio
    async def test_throughput_100_tasks(self):
        """System should handle 100 lightweight tasks within 10 seconds."""
        engine = ExecutionEngine(max_concurrency=10)
        tasks = [{"task_id": f"tp_{i}", "action": "run"} for i in range(100)]
        plan = {"tasks": tasks, "dependencies": {}}
        start = time.monotonic()
        results = await engine.execute_plan(plan)
        elapsed = time.monotonic() - start
        assert len(results) == 100
        assert elapsed < 10.0, f"100 tasks took {elapsed:.3f}s (expected <10s)"
