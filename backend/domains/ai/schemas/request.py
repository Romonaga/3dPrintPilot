from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


class ReconcileOpenAICostsRequest(BaseModel):
    period_start: datetime
    period_end: datetime


class RunAiTaskRequest(BaseModel):
    task_type: str = Field(default="compatibility_explanation", min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=8000)
    context_type: str | None = Field(default=None, max_length=80)
    context_id: str | None = Field(default=None, max_length=120)
    allow_openai_fallback: bool = False
