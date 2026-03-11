"""Task validation — pre-execution safety and feasibility checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_DANGEROUS_ACTIONS = frozenset(
    {"delete_all", "drop_database", "rm_rf", "format_disk"}
)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class TaskValidationSystem:
    """Validates tasks before they are dispatched for execution."""

    def validate_task(self, task: Dict[str, Any]) -> ValidationResult:
        """Run all validation checks on *task*."""
        errors: List[str] = []
        warnings: List[str] = []

        self._check_safety(task, errors, warnings)
        self._check_feasibility(task, errors, warnings)
        self._check_permissions(task, errors, warnings)
        self._check_resources(task, errors, warnings)
        self._check_dependencies(task, errors, warnings)

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning("Task validation failed — errors: %s", errors)
        else:
            logger.debug("Task validation passed (warnings: %s)", warnings)

        return ValidationResult(is_valid=is_valid, warnings=warnings, errors=errors)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_safety(
        self,
        task: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        action = str(task.get("action", "")).lower()
        if action in _DANGEROUS_ACTIONS:
            errors.append(f"Unsafe action requested: '{action}'")

    def _check_feasibility(
        self,
        task: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        if not task.get("task_id") and not task.get("action") and not task.get("objective"):
            warnings.append("Task has no identifiable action or objective")

    def _check_permissions(
        self,
        task: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        required_perms = task.get("required_permissions", [])
        if required_perms:
            warnings.append(f"Task requires permissions: {required_perms}")

    def _check_resources(
        self,
        task: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        mem_req = task.get("memory_required_mb", 0)
        if isinstance(mem_req, (int, float)) and mem_req > 8192:
            warnings.append(f"High memory requirement: {mem_req} MB")

    def _check_dependencies(
        self,
        task: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        deps = task.get("dependencies", [])
        if isinstance(deps, list) and len(deps) > 10:
            warnings.append(f"Task has {len(deps)} dependencies — may impact performance")
