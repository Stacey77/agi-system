"""Centralised application configuration via pydantic-settings."""

from __future__ import annotations

import secrets

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    default_temperature: float = 0.7

    # Auth
    api_key: str | None = None
    api_keys: str | None = None  # JSON array of {key, name, role}
    jwt_secret: str = secrets.token_hex(32)
    jwt_expiry_seconds: int = 3600

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: float = 60.0

    # Redis
    redis_url: str = ""

    # CORS — default to localhost only; override with a comma-separated list in production
    cors_origins: str = "http://localhost:8000"

    @field_validator("cors_origins")
    @classmethod
    def parse_cors(cls, v: str) -> str:
        return v

    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    # Database / persistence
    database_url: str | None = None
    task_db_path: str = "tasks.db"

    # External tools
    web_search_api_key: str | None = None
    web_search_provider: str = "mock"

    # Observability
    otel_service_name: str = "agi-system"
    log_format: str = "json"  # "json" | "text"
    log_level: str = "INFO"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
