from __future__ import annotations

from functools import lru_cache
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PRINTPILOT_", env_file=".env", extra="ignore")

    app_name: str = "3dPrintPilot"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = Field(default="postgresql+psycopg://3dprintpilot:3dprintpilot@localhost:5432/3dprintpilot")
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 1800
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8001",
            "http://127.0.0.1:8001",
            "http://3dprintpilot.local",
            "http://3dprintpilot.local:8001",
            "http://3dprintpilot",
            "http://3dprintpilot:8001",
        ]
    )
    ollama_base_url: str = "http://localhost:11434/api"
    local_llm_default_model: str = "qwen3-coder:30b"
    openai_fallback_enabled: bool = False
    openai_fallback_model: str = "gpt-5.4"
    ai_quality_threshold: float = 0.72
    openai_monthly_budget_usd: Decimal = Decimal("5.00")
    openai_single_request_budget_usd: Decimal = Decimal("0.25")
    field_encryption_key: str | None = None
    field_encryption_key_file: str = ".secrets/field-encryption.key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
