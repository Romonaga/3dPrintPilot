from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PRINTPILOT_", env_file=".env", extra="ignore")

    app_name: str = "3dPrintPilot"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = Field(default="postgresql+psycopg://3dprintpilot:3dprintpilot@localhost:5432/3dprintpilot")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    ollama_base_url: str = "http://localhost:11434/api"
    local_llm_default_model: str = "qwen3-coder:30b"
    openai_fallback_enabled: bool = False
    field_encryption_key: str | None = None
    field_encryption_key_file: str = ".secrets/field-encryption.key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
