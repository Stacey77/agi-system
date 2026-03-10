"""Production environment configuration."""

from __future__ import annotations

from config.environments.base import BaseConfig


class ProductionConfig(BaseConfig):
    """Production settings: strict logging, higher capacity."""

    debug: bool = False
    log_level: str = "WARNING"
    environment: str = "production"
    max_agents: int = 50
