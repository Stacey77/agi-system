"""Tests for WorkforceManager real task queue + agent dispatch wiring."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workforce.workforce_manager import WorkforceManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_factory(agent_name: str = "planning_agent"):
    factory = MagicMock()
    agent = MagicMock()
    agent.process_task = AsyncMock(return_value={"status": "completed"})
    factory.get_agent = MagicMock(
        side_effect=lambda name: agent if name == agent_name else None
    )
    factory.list_agents = MagicMock(return_value=[])
    return factory, agent


def _make_queue():
    q = MagicMock()
    record = MagicMock()
    record.task_id = "task-123"
    q.submit = AsyncMock(return_value=record)
    return q


# ---------------------------------------------------------------------------
# WorkforceManager constructor
# ---------------------------------------------------------------------------


class TestWorkforceManagerInit:
    def test_task_queue_passed_to_dispatcher(self):
        q = _make_queue()
        wm = WorkforceManager(task_queue=q)
        assert wm._dispatcher._queue is q

    def test_no_task_queue_defaults_none(self):
        wm = WorkforceManager()
        assert wm._dispatcher._queue is None

    def test_factory_stored(self):
        factory, _ = _make_factory()
        wm = WorkforceManager(agent_factory=factory)
        assert wm._factory is factory


# ---------------------------------------------------------------------------
# initialize_from_factory
# ---------------------------------------------------------------------------


class TestInitializeFromFactory:
    @pytest.mark.asyncio
    async def test_workers_added_for_each_agent(self):
        factory = MagicMock()
        cfg1 = MagicMock()
        cfg1.name = "planning_agent"
        cfg1.agent_type = MagicMock()
        cfg1.agent_type.value = "planning"
        cfg1.capabilities = ["task_decomposition"]
        agent1 = MagicMock()
        agent1.config = cfg1
        factory.list_agents = MagicMock(return_value=[agent1])

        wm = WorkforceManager(agent_factory=factory)
        await wm.initialize_from_factory()

        workers = wm._pool.list_workers()
        assert len(workers) == 1
        assert workers[0].agent_type == "planning"

    @pytest.mark.asyncio
    async def test_no_factory_does_nothing(self):
        wm = WorkforceManager()
        await wm.initialize_from_factory()
        assert wm._pool.list_workers() == []


# ---------------------------------------------------------------------------
# assign_objective — background task creation
# ---------------------------------------------------------------------------


class TestAssignObjective:
    @pytest.mark.asyncio
    async def test_background_task_created_when_worker_available(self):
        factory, _agent = _make_factory("planning_agent")
        q = _make_queue()
        wm = WorkforceManager(agent_factory=factory, task_queue=q)
        wm._pool.add_worker(name="planning_agent", agent_type="planning", skills=[])

        created_tasks = []
        original_create_task = asyncio.create_task

        def mock_create_task(coro, **kw):
            t = original_create_task(coro, **kw)
            created_tasks.append(t)
            return t

        with patch("asyncio.create_task", side_effect=mock_create_task):
            result = await wm.assign_objective("do something")

        assert result["status"] == "assigned"
        assert len(created_tasks) == 1
        # Let the task run
        await asyncio.gather(*created_tasks, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_no_background_task_when_no_worker(self):
        wm = WorkforceManager()
        created_tasks = []

        with patch(
            "asyncio.create_task",
            side_effect=lambda c, **kw: (
                created_tasks.append(c) or asyncio.ensure_future(c)
            ),
        ):
            result = await wm.assign_objective("do something")

        assert result["status"] == "queued"
        assert len(created_tasks) == 0


# ---------------------------------------------------------------------------
# _execute_via_agent
# ---------------------------------------------------------------------------


class TestExecuteViaAgent:
    @pytest.mark.asyncio
    async def test_calls_process_task_on_matching_agent(self):
        factory, agent = _make_factory("planning_agent")
        wm = WorkforceManager(agent_factory=factory)
        worker = wm._pool.add_worker(
            name="planning_agent", agent_type="planning", skills=[]
        )
        wm._pool.assign_task(worker.worker_id, "task-1")

        await wm._execute_via_agent(
            objective="plan this", task_id="task-1", worker_id=worker.worker_id
        )

        agent.process_task.assert_called_once_with(
            {"objective": "plan this", "task_id": "task-1"}
        )

    @pytest.mark.asyncio
    async def test_complete_task_success_true_on_success(self):
        factory, _agent = _make_factory("planning_agent")
        wm = WorkforceManager(agent_factory=factory)
        worker = wm._pool.add_worker(
            name="planning_agent", agent_type="planning", skills=[]
        )
        wm._pool.assign_task(worker.worker_id, "task-1")

        await wm._execute_via_agent("plan", "task-1", worker.worker_id)

        updated = wm._pool.get_worker(worker.worker_id)
        assert updated.tasks_completed == 1
        assert updated.tasks_failed == 0

    @pytest.mark.asyncio
    async def test_complete_task_failure_on_exception(self):
        factory, agent = _make_factory("planning_agent")
        agent.process_task = AsyncMock(side_effect=RuntimeError("boom"))
        wm = WorkforceManager(agent_factory=factory)
        worker = wm._pool.add_worker(
            name="planning_agent", agent_type="planning", skills=[]
        )
        wm._pool.assign_task(worker.worker_id, "task-1")

        await wm._execute_via_agent("plan", "task-1", worker.worker_id)

        updated = wm._pool.get_worker(worker.worker_id)
        assert updated.tasks_failed == 1

    @pytest.mark.asyncio
    async def test_no_agent_found_marks_complete_success(self):
        factory = MagicMock()
        factory.get_agent = MagicMock(return_value=None)
        wm = WorkforceManager(agent_factory=factory)
        worker = wm._pool.add_worker(
            name="unknown_agent", agent_type="unknown", skills=[]
        )
        wm._pool.assign_task(worker.worker_id, "task-1")

        await wm._execute_via_agent("do it", "task-1", worker.worker_id)

        updated = wm._pool.get_worker(worker.worker_id)
        # graceful: no crash, task counted as completed
        assert updated.tasks_completed == 1

    @pytest.mark.asyncio
    async def test_missing_worker_id_does_not_crash(self):
        wm = WorkforceManager()
        # Should not raise
        await wm._execute_via_agent("do it", "task-x", "nonexistent-worker")
