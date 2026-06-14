from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReconcileOpenAICostsRequest(BaseModel):
    period_start: datetime
    period_end: datetime
