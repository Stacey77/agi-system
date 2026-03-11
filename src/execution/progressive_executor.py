"""Progressive executor — phase-based execution with checkpoints and pause/resume."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProgressiveResult:
    """Result of a progressive execution."""

    success: bool
    phases_completed: List[str] = field(default_factory=list)
    phases_skipped: List[str] = field(default_factory=list)
    total_duration: float = 0.0
    error: Optional[str] = None
    output: Dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """Saves and loads execution checkpoints."""

    def __init__(self) -> None:
        self._checkpoints: Dict[str, Dict[str, Any]] = {}

    def save(self, phase_id: str, data: Dict[str, Any]) -> None:
        self._checkpoints[phase_id] = dict(data)
        logger.debug("Checkpoint saved for phase '%s'", phase_id)

    def load(self, phase_id: str) -> Optional[Dict[str, Any]]:
        return self._checkpoints.get(phase_id)

    def list_checkpoints(self) -> List[str]:
        return list(self._checkpoints.keys())


class ProgressTracker:
    """Tracks progress through phases."""

    def __init__(self, total_phases: int) -> None:
        self._total = total_phases
        self._completed = 0
        self._current: Optional[str] = None

    def start_phase(self, phase_id: str) -> None:
        self._current = phase_id
        logger.info(
            "Phase '%s' started (%d/%d)", phase_id, self._completed + 1, self._total
        )

    def complete_phase(self) -> None:
        self._completed += 1
        self._current = None

    @property
    def progress(self) -> float:
        if self._total == 0:
            return 1.0
        return self._completed / self._total

    @property
    def current_phase(self) -> Optional[str]:
        return self._current


class ProgressiveExecutor:
    """Executes complex tasks phase by phase with pause/resume support."""

    def __init__(self) -> None:
        self._checkpoints = CheckpointManager()
        self._paused = False
        self._stopped = False

    def pause(self) -> None:
        """Pause execution after the current phase completes."""
        self._paused = True
        logger.info("ProgressiveExecutor paused")

    def resume(self) -> None:
        """Resume paused execution."""
        self._paused = False
        logger.info("ProgressiveExecutor resumed")

    def stop(self) -> None:
        """Stop execution entirely."""
        self._stopped = True
        logger.info("ProgressiveExecutor stopped")

    async def execute_progressively(
        self, complex_task: Dict[str, Any]
    ) -> ProgressiveResult:
        """Execute *complex_task* phase by phase.

        The task must contain a ``phases`` key with a list of phase
        dictionaries, each with at minimum a ``phase_id`` field.
        """
        phases: List[Dict[str, Any]] = complex_task.get("phases", [])
        if not phases:
            # Derive phases from a flat task
            phases = [
                {"phase_id": "execute", "action": complex_task.get("action", "run")}
            ]

        tracker = ProgressTracker(len(phases))
        start_time = time.monotonic()
        completed: List[str] = []
        skipped: List[str] = []
        output: Dict[str, Any] = {}
        self._stopped = False

        for phase in phases:
            if self._stopped:
                skipped.extend(p["phase_id"] for p in phases[len(completed):])
                break

            while self._paused and not self._stopped:
                await asyncio.sleep(0.1)

            phase_id = phase.get("phase_id", f"phase_{len(completed)}")

            # Resume from checkpoint if available
            cached = self._checkpoints.load(phase_id)
            if cached is not None:
                output[phase_id] = cached
                completed.append(phase_id)
                logger.debug("Phase '%s' restored from checkpoint", phase_id)
                continue

            tracker.start_phase(phase_id)
            try:
                result = await self._execute_phase(phase)
                output[phase_id] = result
                self._checkpoints.save(phase_id, result)
                tracker.complete_phase()
                completed.append(phase_id)
            except Exception as exc:  # noqa: BLE001
                elapsed = time.monotonic() - start_time
                return ProgressiveResult(
                    success=False,
                    phases_completed=completed,
                    phases_skipped=skipped,
                    total_duration=elapsed,
                    error=str(exc),
                    output=output,
                )

        elapsed = time.monotonic() - start_time
        return ProgressiveResult(
            success=len(skipped) == 0,
            phases_completed=completed,
            phases_skipped=skipped,
            total_duration=elapsed,
            output=output,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _execute_phase(self, phase: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single phase — override for real work."""
        await asyncio.sleep(0)  # yield control
        return {"phase_id": phase.get("phase_id"), "status": "completed"}
