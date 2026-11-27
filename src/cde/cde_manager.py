"""CDE manager — lifecycle management for cloud development environments."""

from __future__ import annotations

import logging

from src.cde.cde_environment import (
    CDEEnvironment,
    CDEResources,
    CDERuntime,
    CDEStatus,
)

logger = logging.getLogger(__name__)


class CDEManager:
    """Manages create / start / stop / delete lifecycle of CDEs."""

    def __init__(self) -> None:
        self._environments: dict[str, CDEEnvironment] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_environment(
        self,
        name: str = "default-cde",
        runtime: CDERuntime = CDERuntime.PYTHON,
        runtime_version: str = "latest",
        owner: str = "",
        repository_url: str | None = None,
        branch: str = "main",
        resources: CDEResources | None = None,
        env_vars: dict[str, str] | None = None,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> CDEEnvironment:
        """Provision a new CDE and register it."""
        env = CDEEnvironment(
            name=name,
            runtime=runtime,
            runtime_version=runtime_version,
            owner=owner,
            repository_url=repository_url,
            branch=branch,
            resources=resources or CDEResources(),
            env_vars=env_vars or {},
            tags=tags or [],
            metadata=metadata or {},
        )
        self._environments[env.env_id] = env
        # Simulate immediate transition to RUNNING for in-process manager
        env.transition_to(CDEStatus.RUNNING)
        logger.info("CDEManager: created env '%s' (id=%s)", name, env.env_id)
        return env

    def get_environment(self, env_id: str) -> CDEEnvironment | None:
        return self._environments.get(env_id)

    def list_environments(
        self,
        owner: str | None = None,
        status: CDEStatus | None = None,
    ) -> list[CDEEnvironment]:
        envs = list(self._environments.values())
        if owner:
            envs = [e for e in envs if e.owner == owner]
        if status:
            envs = [e for e in envs if e.status == status]
        return envs

    def stop_environment(self, env_id: str) -> bool:
        env = self._environments.get(env_id)
        if env is None:
            return False
        if env.status not in (CDEStatus.RUNNING, CDEStatus.PROVISIONING):
            return False
        env.transition_to(CDEStatus.STOPPED)
        logger.info("CDEManager: stopped env '%s'", env_id)
        return True

    def start_environment(self, env_id: str) -> bool:
        env = self._environments.get(env_id)
        if env is None:
            return False
        if env.status != CDEStatus.STOPPED:
            return False
        env.transition_to(CDEStatus.RUNNING)
        logger.info("CDEManager: started env '%s'", env_id)
        return True

    def delete_environment(self, env_id: str) -> bool:
        env = self._environments.get(env_id)
        if env is None:
            return False
        env.transition_to(CDEStatus.DELETED)
        del self._environments[env_id]
        logger.info("CDEManager: deleted env '%s'", env_id)
        return True

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def running_count(self) -> int:
        return sum(
            1 for e in self._environments.values() if e.status == CDEStatus.RUNNING
        )

    def total_count(self) -> int:
        return len(self._environments)
