from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Protocol
from uuid import uuid4

from backend.domains.ai.store import AiAccountingStore
from local_ai_accounting.estimate import MONEY_QUANT
from local_ai_accounting.openai_admin_client import OpenAIAdminClient
from local_ai_accounting.reconcile import reconcile_cost_bucket


class OpenAICostClient(Protocol):
    def fetch_costs(
        self,
        *,
        start_time: int,
        end_time: int | None = None,
        bucket_width: str = "1d",
        group_by: list[str] | None = None,
        limit: int = 180,
    ) -> dict[str, Any]:
        """Fetch OpenAI organization cost buckets."""


@dataclass(frozen=True)
class CostReconciliationResult:
    run_id: str
    status: str
    period_start: datetime
    period_end: datetime
    estimated_total_usd: Decimal
    final_total_usd: Decimal | None
    event_count: int
    updated_event_count: int
    bucket_count: int
    details: dict[str, Any]


class OpenAICostReconciliationService:
    def __init__(self, store: AiAccountingStore, client: OpenAICostClient) -> None:
        self._store = store
        self._client = client

    def reconcile_period(self, *, period_start: datetime, period_end: datetime) -> CostReconciliationResult:
        start = _ensure_utc(period_start)
        end = _ensure_utc(period_end)
        if end <= start:
            raise ValueError("period_end must be after period_start")

        run_id = str(uuid4())
        events = self._store.list_reconcilable_events(start, end)
        estimated_total = sum((event.estimated_cost_usd for event in events), Decimal("0")).quantize(MONEY_QUANT)
        run_details: dict[str, Any] = {
            "source": "openai_organization_costs",
            "bucket_width": "1d",
            "requested_group_by": [],
            "event_count": len(events),
        }
        self._store.create_reconciliation_run(
            run_id=run_id,
            period_start=start,
            period_end=end,
            estimated_total_usd=estimated_total,
            details=run_details,
        )

        try:
            payload = self._client.fetch_costs(
                start_time=int(start.timestamp()),
                end_time=int(end.timestamp()),
                bucket_width="1d",
                limit=180,
            )
            buckets = payload.get("data") or []
            final_total = extract_openai_cost_total_usd(buckets)
            updates = reconcile_cost_bucket(events, verified_cost_usd=final_total, reconciliation_run_id=run_id)
            self._store.apply_event_updates(updates)
            status = "completed"
            details = {
                **run_details,
                "bucket_count": len(buckets),
                "updated_event_count": len(updates),
                "openai_cost_bucket_count": len(buckets),
                "openai_raw_costs": _compact_cost_buckets(buckets),
            }
            self._store.complete_reconciliation_run(
                run_id,
                status=status,
                final_total_usd=final_total,
                details=details,
            )
            return CostReconciliationResult(
                run_id=run_id,
                status=status,
                period_start=start,
                period_end=end,
                estimated_total_usd=estimated_total,
                final_total_usd=final_total,
                event_count=len(events),
                updated_event_count=len(updates),
                bucket_count=len(buckets),
                details=details,
            )
        except Exception as exc:
            details = {**run_details, "error": str(exc)}
            self._store.complete_reconciliation_run(run_id, status="failed", final_total_usd=None, details=details)
            raise


def create_openai_cost_reconciliation_service(
    *,
    store: AiAccountingStore,
    admin_api_key: str,
) -> OpenAICostReconciliationService:
    return OpenAICostReconciliationService(store, OpenAIAdminClient(admin_api_key=admin_api_key))


def extract_openai_cost_total_usd(buckets: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0")
    for bucket in buckets:
        for result in bucket.get("results") or []:
            amount = result.get("amount") or {}
            currency = str(amount.get("currency") or "usd").lower()
            if currency != "usd":
                continue
            total += Decimal(str(amount.get("value") or "0"))
    return total.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _compact_cost_buckets(buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted = []
    for bucket in buckets:
        compacted.append(
            {
                "start_time": bucket.get("start_time"),
                "end_time": bucket.get("end_time"),
                "results": [
                    {
                        "amount": result.get("amount"),
                        "line_item": result.get("line_item"),
                        "project_id": result.get("project_id"),
                        "api_key_id": result.get("api_key_id"),
                        "quantity": result.get("quantity"),
                    }
                    for result in (bucket.get("results") or [])
                ],
            }
        )
    return compacted


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
