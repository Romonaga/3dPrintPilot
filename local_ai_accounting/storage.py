from __future__ import annotations

from datetime import datetime
from typing import Protocol

from local_ai_accounting.models import EventCostUpdate, UsageCostEvent


class CostAccountingStore(Protocol):
    def list_estimated_events(self, start: datetime, end: datetime) -> list[UsageCostEvent]:
        """Return events that need final-cost reconciliation."""

    def save_reconciliation_run(self, run: dict) -> None:
        """Persist metadata for a reconciliation attempt."""

    def update_event_final_cost(self, update: EventCostUpdate) -> None:
        """Persist final cost fields for one event."""

    def save_daily_rollup(self, rollup: dict) -> None:
        """Persist daily estimated-vs-final cost summary."""

