"""CDE agent — intelligent orchestration of cloud development environments."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.agents.base_agent import AgentConfig, BaseAgent
from src.cde.cde_environment import CDEResources, CDERuntime, CDEStatus
from src.cde.cde_manager import CDEManager

logger = logging.getLogger(__name__)


class CDEAgent(BaseAgent):
    """Orchestrates cloud development environments via natural-language tasks.

    Supported actions: ``create``, ``start``, ``stop``, ``delete``, ``list``, ``status``.
    """

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
        cde_manager: Optional[CDEManager] = None,
    ) -> None:
        super().__init__(config, execution_agent)
        self.cde_manager = cde_manager or CDEManager()

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a CDE management task."""
        action = task.get("action", "list")
        logger.info("CDEAgent action='%s'", action)

        dispatcher = {
            "create": self._handle_create,
            "start": self._handle_start,
            "stop": self._handle_stop,
            "delete": self._handle_delete,
            "list": self._handle_list,
            "status": self._handle_status,
        }
        handler = dispatcher.get(action)
        if handler is None:
            result: Dict[str, Any] = {
                "status": "error",
                "error": f"Unknown action '{action}'",
            }
        else:
            result = await handler(task)

        self._record_task(task, result)
        return result

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    async def _handle_create(self, task: Dict[str, Any]) -> Dict[str, Any]:
        runtime_str = task.get("runtime", "python")
        try:
            runtime = CDERuntime(runtime_str)
        except ValueError:
            runtime = CDERuntime.GENERIC

        resources_data = task.get("resources", {})
        resources = CDEResources(
            cpu_cores=resources_data.get("cpu_cores", 1.0),
            memory_gb=resources_data.get("memory_gb", 2.0),
            storage_gb=resources_data.get("storage_gb", 10.0),
            gpu_count=resources_data.get("gpu_count", 0),
        )
        env = self.cde_manager.create_environment(
            name=task.get("name", "cde-env"),
            runtime=runtime,
            runtime_version=task.get("runtime_version", "latest"),
            owner=task.get("owner", ""),
            repository_url=task.get("repository_url"),
            branch=task.get("branch", "main"),
            resources=resources,
            env_vars=task.get("env_vars", {}),
            tags=task.get("tags", []),
        )
        return {"status": "completed", "action": "create", "environment": env.to_dict()}

    async def _handle_start(self, task: Dict[str, Any]) -> Dict[str, Any]:
        env_id = task.get("env_id", "")
        success = self.cde_manager.start_environment(env_id)
        return {
            "status": "completed" if success else "error",
            "action": "start",
            "env_id": env_id,
            "started": success,
        }

    async def _handle_stop(self, task: Dict[str, Any]) -> Dict[str, Any]:
        env_id = task.get("env_id", "")
        success = self.cde_manager.stop_environment(env_id)
        return {
            "status": "completed" if success else "error",
            "action": "stop",
            "env_id": env_id,
            "stopped": success,
        }

    async def _handle_delete(self, task: Dict[str, Any]) -> Dict[str, Any]:
        env_id = task.get("env_id", "")
        success = self.cde_manager.delete_environment(env_id)
        return {
            "status": "completed" if success else "error",
            "action": "delete",
            "env_id": env_id,
            "deleted": success,
        }

    async def _handle_list(self, task: Dict[str, Any]) -> Dict[str, Any]:
        owner = task.get("owner")
        status_str = task.get("filter_status")
        status_filter: Optional[CDEStatus] = None
        if status_str:
            try:
                status_filter = CDEStatus(status_str)
            except ValueError:
                pass
        envs = self.cde_manager.list_environments(owner=owner, status=status_filter)
        return {
            "status": "completed",
            "action": "list",
            "environments": [e.to_dict() for e in envs],
            "total": len(envs),
        }

    async def _handle_status(self, task: Dict[str, Any]) -> Dict[str, Any]:
        env_id = task.get("env_id", "")
        env = self.cde_manager.get_environment(env_id)
        if env is None:
            return {"status": "error", "error": f"Environment '{env_id}' not found"}
        return {"status": "completed", "action": "status", "environment": env.to_dict()}
