from __future__ import annotations

from pydantic import BaseModel, Field


class RunCompatibilityChecksRequest(BaseModel):
    scan_run_id: int = Field(ge=1)
    printer_ids: list[int] | None = Field(default=None, max_length=50)
    max_candidates: int = Field(default=25, ge=1, le=100)
