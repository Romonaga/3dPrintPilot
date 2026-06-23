from __future__ import annotations

from pydantic import BaseModel, Field


class UpsertProviderSecretRequest(BaseModel):
    value: str = Field(min_length=1, max_length=1200)


class UpdateAuthSettingsRequest(BaseModel):
    session_timeout_minutes: int = Field(ge=5, le=43_200)
