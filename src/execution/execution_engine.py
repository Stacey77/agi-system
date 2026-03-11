"""Execution engine — core engine with dependency-aware concurrent task execution."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.execution.error_handler import ErrorHandler
from src.execution.task_validation import TaskValidationSystem

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Lifecycle states for a single task execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ExecutionResult:
    """Result of executing a single task."""

    task_id: str
    status: ExecutionStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionEngine:
    """Core execution engine with resource management and dependency handling."""

    def __init__(self, max_concurrency: int = 5) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._validator = TaskValidationSystem()
        self._error_handler = ErrorHandler()
        self._resources: Dict[str, Any] = {}
        logger.info("ExecutionEngine initialised (max_concurrency=%d)", max_concurrency)

    async def execute_plan(self, plan: Dict[str, Any]) -> List[ExecutionResult]:
        """Execute all tasks in *plan* respecting declared dependencies."""
        tasks = plan.get("tasks", [])
        if not tasks:
            logger.warning("execute_plan called with empty task list")
            return []
        return await self._execute_with_dependencies(plan)

    # ------------------------------------------------------------------
    # Dependency-aware execution
    # ------------------------------------------------------------------

    async def _execute_with_dependencies(
        self, plan: Dict[str, Any]
    ) -> List[ExecutionResult]:
        tasks: List[Dict[str, Any]] = plan.get("tasks", [])
        dependencies: Dict[str, List[str]] = plan.get("dependencies", {})

        # Topological sort
        ordered = self._topological_sort(tasks, dependencies)

        results: Dict[str, ExecutionResult] = {}
        for batch in ordered:
            batch_coros = [
                self._execute_single_task(task, results) for task in batch
            ]
            batch_results = await asyncio.gather(*batch_coros, return_exceptions=True)
            for task, br in zip(batch, batch_results):
                tid = task.get("task_id", "unknown")
                if isinstance(br, Exception):
                    results[tid] = ExecutionResult(
                        task_id=tid,
                        status=ExecutionStatus.FAILED,
                        error=str(br),
                    )
                else:
                    results[tid] = br

        return list(results.values())

    async def _execute_single_task(
        self,
        task: Dict[str, Any],
        context: Dict[str, ExecutionResult],
    ) -> ExecutionResult:
        task_id = task.get("task_id", "unknown")

        # Validate
        validation = self._validator.validate_task(task)
        if not validation.is_valid:
            return ExecutionResult(
                task_id=task_id,
                status=ExecutionStatus.FAILED,
                error=f"Validation failed: {validation.errors}",
            )

        async with self._semaphore:
            await self._allocate_resources(task)
            start = time.monotonic()
            try:
                result = await self._dispatch(task, context)
                elapsed = time.monotonic() - start
                await self._release_resources(task)
                return ExecutionResult(
                    task_id=task_id,
                    status=ExecutionStatus.COMPLETED,
                    result=result,
                    execution_time=elapsed,
                )
            except Exception as exc:  # noqa: BLE001
                elapsed = time.monotonic() - start
                recovery = self._error_handler.create_recovery_plan(task, exc)
                logger.error(
                    "Task '%s' failed: %s (recovery: %s)",
                    task_id,
                    exc,
                    recovery.steps,
                )
                await self._release_resources(task)
                return ExecutionResult(
                    task_id=task_id,
                    status=ExecutionStatus.FAILED,
                    error=str(exc),
                    execution_time=elapsed,
                    metadata={"recovery_steps": recovery.steps},
                )

    # ------------------------------------------------------------------
    # Dispatch by task type
    # ------------------------------------------------------------------

    async def _dispatch(
        self, task: Dict[str, Any], context: Dict[str, ExecutionResult]
    ) -> Any:
        task_type = task.get("type", "generic")
        handlers = {
            "tool_execution": self._run_tool,
            "code_execution": self._run_code,
            "api_call": self._run_api_call,
            "file_operation": self._run_file_op,
        }
        handler = handlers.get(task_type, self._run_generic)
        return await handler(task, context)

    async def _run_tool(
        self, task: Dict[str, Any], context: Dict[str, ExecutionResult]
    ) -> Any:
        return {"type": "tool_execution", "task_id": task.get("task_id")}

    async def _run_code(
        self, task: Dict[str, Any], context: Dict[str, ExecutionResult]
    ) -> Any:
        return {"type": "code_execution", "task_id": task.get("task_id")}

    async def _run_api_call(
        self, task: Dict[str, Any], context: Dict[str, ExecutionResult]
    ) -> Any:
        return {"type": "api_call", "task_id": task.get("task_id")}

    async def _run_file_op(
        self, task: Dict[str, Any], context: Dict[str, ExecutionResult]
    ) -> Any:
        return {"type": "file_operation", "task_id": task.get("task_id")}

    async def _run_generic(
        self, task: Dict[str, Any], context: Dict[str, ExecutionResult]
    ) -> Any:
        await asyncio.sleep(0)  # yield
        return {"type": "generic", "task_id": task.get("task_id"), "status": "done"}

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    async def _allocate_resources(self, task: Dict[str, Any]) -> None:
        task_id = task.get("task_id", "unknown")
        self._resources[task_id] = {"allocated": True}

    async def _release_resources(self, task: Dict[str, Any]) -> None:
        task_id = task.get("task_id", "unknown")
        self._resources.pop(task_id, None)

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------

    def _topological_sort(
        self,
        tasks: List[Dict[str, Any]],
        dependencies: Dict[str, List[str]],
    ) -> List[List[Dict[str, Any]]]:
        """Return tasks grouped into sequential batches (Kahn's algorithm)."""
        task_map = {t["task_id"]: t for t in tasks if "task_id" in t}
        in_degree: Dict[str, int] = {tid: 0 for tid in task_map}
        reverse_deps: Dict[str, List[str]] = {tid: [] for tid in task_map}

        for tid, deps in dependencies.items():
            for dep in deps:
                if dep in in_degree and tid in in_degree:
                    in_degree[tid] += 1
                    reverse_deps[dep].append(tid)

        batches: List[List[Dict[str, Any]]] = []
        ready = [tid for tid, deg in in_degree.items() if deg == 0]

        while ready:
            batch = [task_map[tid] for tid in ready if tid in task_map]
            if batch:
                batches.append(batch)
            next_ready: List[str] = []
            for tid in ready:
                for dependent in reverse_deps.get(tid, []):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_ready.append(dependent)
            ready = next_ready

        # Append any remaining tasks that weren't covered
        scheduled = {t["task_id"] for batch in batches for t in batch}
        remaining = [t for t in tasks if t.get("task_id") not in scheduled]
        if remaining:
            batches.append(remaining)

        return batches
