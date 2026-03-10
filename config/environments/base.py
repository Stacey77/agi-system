"""Base configuration using Pydantic BaseSettings."""

from __future__ import annotations

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    """Base application configuration — all environments inherit from this."""

    # Application
    app_name: str = Field(default="AGI System")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # LLM
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    default_model: str = Field(default="gpt-4")

    # Database
    database_url: str = Field(default="sqlite:///./agi_system.db")
    redis_url: str = Field(default="redis://localhost:6379")

    # Agent
    max_agents: int = Field(default=10)
    agent_timeout: int = Field(default=300)
    default_temperature: float = Field(default=0.7)

    # API Auth
    api_key: Optional[str] = Field(default=None)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_config(env: str = "development") -> BaseConfig:
    """Factory: return the appropriate config for *env*."""
    from config.environments.development import DevelopmentConfig
    from config.environments.production import ProductionConfig

    configs = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
    }
    cls = configs.get(env, DevelopmentConfig)
    return cls()
