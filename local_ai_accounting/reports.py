from __future__ import annotations

import csv
from io import StringIO
from typing import Iterable

from local_ai_accounting.models import EventCostUpdate


def cost_updates_to_csv(updates: Iterable[EventCostUpdate]) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "event_id",
            "estimated_cost_usd",
            "final_cost_usd",
            "cost_status",
            "cost_discrepancy_usd",
            "reconciliation_run_id",
            "allocation_method",
        ],
    )
    writer.writeheader()
    for update in updates:
        writer.writerow(
            {
                "event_id": update.event_id,
                "estimated_cost_usd": str(update.estimated_cost_usd),
                "final_cost_usd": str(update.final_cost_usd),
                "cost_status": str(update.cost_status),
                "cost_discrepancy_usd": str(update.cost_discrepancy_usd),
                "reconciliation_run_id": update.reconciliation_run_id,
                "allocation_method": update.allocation_method,
            }
        )
    return output.getvalue()

