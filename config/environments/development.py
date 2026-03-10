"""Development environment configuration."""

from __future__ import annotations

from config.environments.base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """Development-mode settings: verbose logging, debug enabled."""

    debug: bool = True
    log_level: str = "DEBUG"
    environment: str = "development"
