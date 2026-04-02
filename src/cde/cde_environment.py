"""CDE environment data models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class CDEStatus(str, Enum):
    """Lifecycle status of a cloud development environment."""

    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"


class CDERuntime(str, Enum):
    """Supported container runtimes for CDEs."""

    PYTHON = "python"
    NODE = "node"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    GENERIC = "generic"


@dataclass
class CDEResources:
    """Compute resource specification for a CDE."""

    cpu_cores: float = 1.0
    memory_gb: float = 2.0
    storage_gb: float = 10.0
    gpu_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_cores": self.cpu_cores,
            "memory_gb": self.memory_gb,
            "storage_gb": self.storage_gb,
            "gpu_count": self.gpu_count,
        }


@dataclass
class CDEEnvironment:
    """Represents a single cloud development environment instance."""

    env_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "default-cde"
    runtime: CDERuntime = CDERuntime.PYTHON
    runtime_version: str = "latest"
    status: CDEStatus = CDEStatus.PROVISIONING
    resources: CDEResources = field(default_factory=CDEResources)
    owner: str = ""
    repository_url: Optional[str] = None
    branch: str = "main"
    env_vars: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, status: CDEStatus) -> None:
        """Transition the environment to a new status."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "env_id": self.env_id,
            "name": self.name,
            "runtime": self.runtime,
            "runtime_version": self.runtime_version,
            "status": self.status,
            "resources": self.resources.to_dict(),
            "owner": self.owner,
            "repository_url": self.repository_url,
            "branch": self.branch,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
