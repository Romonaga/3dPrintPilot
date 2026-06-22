from __future__ import annotations

from pydantic import BaseModel, Field


class SiteScanRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)
    site_key: str = Field(default="auto", min_length=1, max_length=80)
    max_depth: int = Field(default=1, ge=0, le=3)
    max_pages: int = Field(default=50, ge=1, le=250)
    max_runtime_seconds: int = Field(default=300, ge=30, le=1800)
    same_domain_only: bool = True
    allowed_hosts: list[str] = Field(default_factory=list, max_length=25)
    per_host_concurrency: int = Field(default=1, ge=1, le=4)


class UpdateSiteAdapterRequest(BaseModel):
    enabled: bool


class UpsertSiteAuthProfileRequest(BaseModel):
    auth_mode: str = Field(..., min_length=1, max_length=40)
    secret_value: str | None = Field(default=None, max_length=8192)
    label: str | None = Field(default=None, max_length=160)
    account_identifier: str | None = Field(default=None, max_length=255)
    header_name: str | None = Field(default=None, max_length=120)
    enabled: bool = True


class StartSiteAuthBrowserLinkRequest(BaseModel):
    label: str | None = Field(default=None, max_length=160)
    account_identifier: str | None = Field(default=None, max_length=255)
