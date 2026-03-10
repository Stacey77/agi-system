"""Unit tests for the execution engine, validation, error handler, and rollback."""

from __future__ import annotations

import pytest

from src.execution.error_handler import ErrorHandler
from src.execution.execution_agent import ExecutionAgent
from src.execution.execution_engine import ExecutionEngine, ExecutionStatus
from src.execution.progressive_executor import ProgressiveExecutor
from src.execution.result_validation import ResultValidationSystem
from src.execution.rollback_manager import RollbackManager
from src.execution.task_validation import TaskValidationSystem


# ---------------------------------------------------------------------------
# TaskValidationSystem
# ---------------------------------------------------------------------------

class TestTaskValidation:
    def test_valid_task(self):
        system = TaskValidationSystem()
        result = system.validate_task({"task_id": "t1", "action": "research"})
        assert result.is_valid
        assert result.errors == []

    def test_unsafe_action_rejected(self):
        system = TaskValidationSystem()
        result = system.validate_task({"task_id": "t2", "action": "delete_all"})
        assert not result.is_valid
        assert any("Unsafe" in e for e in result.errors)

    def test_high_memory_generates_warning(self):
        system = TaskValidationSystem()
        result = system.validate_task({"task_id": "t3", "action": "run", "memory_required_mb": 9000})
        assert result.is_valid  # warning, not error
        assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# ResultValidationSystem
# ---------------------------------------------------------------------------

class TestResultValidation:
    def test_valid_result(self):
        system = ResultValidationSystem()
        task = {"task_id": "t1"}
        result = system.validate_result(task, {"data": "some output"})
        assert result.is_valid

    def test_none_result_is_invalid(self):
        system = ResultValidationSystem()
        task = {"task_id": "t1"}
        result = system.validate_result(task, None)
        assert not result.is_valid

    def test_required_fields_completeness(self):
        system = ResultValidationSystem()
        task = {"task_id": "t1", "required_output_fields": ["name", "status"]}
        result = system.validate_result(task, {"name": "test"})
        assert result.completeness == 0.5


# ---------------------------------------------------------------------------
# ErrorHandler
# ---------------------------------------------------------------------------

class TestErrorHandler:
    def test_network_error_classification(self):
        handler = ErrorHandler()
        analysis = handler.analyze_error(ConnectionError("timeout occurred"), {})
        assert analysis.error_type == "network"

    def test_permission_error_classification(self):
        handler = ErrorHandler()
        analysis = handler.analyze_error(PermissionError("permission denied"), {})
        assert analysis.error_type == "permission"

    def test_recovery_plan_for_network(self):
        handler = ErrorHandler()
        plan = handler.create_recovery_plan({}, ConnectionError("network timeout"))
        assert plan.should_retry is True
        assert len(plan.steps) > 0

    def test_recovery_plan_for_permission(self):
        handler = ErrorHandler()
        plan = handler.create_recovery_plan({}, PermissionError("forbidden"))
        assert plan.should_retry is False


# ---------------------------------------------------------------------------
# ExecutionEngine
# ---------------------------------------------------------------------------

class TestExecutionEngine:
    @pytest.mark.asyncio
    async def test_execute_empty_plan(self):
        engine = ExecutionEngine()
        results = await engine.execute_plan({"tasks": []})
        assert results == []

    @pytest.mark.asyncio
    async def test_execute_single_task(self):
        engine = ExecutionEngine()
        plan = {
            "tasks": [{"task_id": "t1", "action": "run"}],
            "dependencies": {},
        }
        results = await engine.execute_plan(plan)
        assert len(results) == 1
        assert results[0].task_id == "t1"
        assert results[0].status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_multiple_tasks_with_deps(self):
        engine = ExecutionEngine()
        plan = {
            "tasks": [
                {"task_id": "t1", "action": "step1"},
                {"task_id": "t2", "action": "step2"},
            ],
            "dependencies": {"t2": ["t1"]},
        }
        results = await engine.execute_plan(plan)
        assert len(results) == 2
        statuses = {r.task_id: r.status for r in results}
        assert statuses["t1"] == ExecutionStatus.COMPLETED
        assert statuses["t2"] == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_unsafe_task_fails_validation(self):
        engine = ExecutionEngine()
        plan = {
            "tasks": [{"task_id": "bad", "action": "delete_all"}],
            "dependencies": {},
        }
        results = await engine.execute_plan(plan)
        assert results[0].status == ExecutionStatus.FAILED


# ---------------------------------------------------------------------------
# ExecutionAgent
# ---------------------------------------------------------------------------

class TestExecutionAgent:
    @pytest.mark.asyncio
    async def test_validate_plan(self):
        agent = ExecutionAgent()
        plan = {"tasks": [{"task_id": "t1", "action": "process"}]}
        result = await agent.validate_plan(plan)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_execute_plan(self):
        agent = ExecutionAgent()
        plan = {"tasks": [{"task_id": "t1", "action": "process"}], "dependencies": {}}
        result = await agent.execute_plan(plan)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_plan_not_executed(self):
        agent = ExecutionAgent()
        plan = {"tasks": [{"task_id": "x", "action": "delete_all"}]}
        result = await agent.execute_plan(plan)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# RollbackManager
# ---------------------------------------------------------------------------

class TestRollbackManager:
    @pytest.mark.asyncio
    async def test_successful_sequence(self):
        manager = RollbackManager()
        tasks = [{"task_id": "t1"}, {"task_id": "t2"}]
        result = await manager.execute_with_rollback(tasks)
        assert result.success is True
        assert "t1" in result.completed_tasks
        assert "t2" in result.completed_tasks

    @pytest.mark.asyncio
    async def test_rollback_on_failure(self):
        manager = RollbackManager()

        async def failing_executor(task):
            if task["task_id"] == "t2":
                raise RuntimeError("Simulated failure")
            return {"ok": True}

        tasks = [{"task_id": "t1"}, {"task_id": "t2"}, {"task_id": "t3"}]
        result = await manager.execute_with_rollback(tasks, executor=failing_executor)
        assert result.success is False
        assert "t1" in result.completed_tasks
        assert result.error is not None


# ---------------------------------------------------------------------------
# ProgressiveExecutor
# ---------------------------------------------------------------------------

class TestProgressiveExecutor:
    @pytest.mark.asyncio
    async def test_execute_phases(self):
        executor = ProgressiveExecutor()
        task = {
            "phases": [
                {"phase_id": "phase_1"},
                {"phase_id": "phase_2"},
            ]
        }
        result = await executor.execute_progressively(task)
        assert result.success is True
        assert len(result.phases_completed) == 2

    @pytest.mark.asyncio
    async def test_execute_empty_phases(self):
        executor = ProgressiveExecutor()
        result = await executor.execute_progressively({"action": "run"})
        assert result.success is True
