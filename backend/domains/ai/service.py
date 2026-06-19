from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Protocol
from uuid import uuid4

from backend.domains.ai.store import AiAccountingStore
from local_ai_accounting.estimate import MONEY_QUANT
from local_ai_accounting.models import CostStatus
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


@dataclass(frozen=True)
class AiTaskInput:
    task_type: str
    prompt: str
    context_type: str | None = None
    context_id: str | None = None
    allow_openai_fallback: bool = False
    user_id: int | None = None


@dataclass(frozen=True)
class AiTaskResult:
    provider: str
    model_name: str
    task_type: str
    output_text: str
    quality_score: float
    fallback_used: bool
    fallback_reason: str | None
    estimated_cost_usd: Decimal
    cost_status: str
    usage_event_id: int | None


class BudgetExceededError(ValueError):
    pass


class AiTaskRunner:
    def __init__(
        self,
        *,
        store: AiAccountingStore,
        local_model: str,
        openai_model: str,
        quality_threshold: float,
        openai_fallback_enabled: bool,
        openai_api_token_configured: bool,
        monthly_budget_usd: Decimal,
        single_request_budget_usd: Decimal,
        month_start: datetime | None = None,
    ) -> None:
        self._store = store
        self._local_model = local_model
        self._openai_model = openai_model
        self._quality_threshold = quality_threshold
        self._openai_fallback_enabled = openai_fallback_enabled
        self._openai_api_token_configured = openai_api_token_configured
        self._monthly_budget_usd = monthly_budget_usd
        self._single_request_budget_usd = single_request_budget_usd
        self._month_start = month_start

    def run(self, task: AiTaskInput) -> AiTaskResult:
        local_text = _local_response(task.prompt)
        local_quality = score_local_quality(local_text, task.prompt)
        fallback_reason = fallback_reason_for_quality(local_quality, self._quality_threshold)
        should_fallback = (
            fallback_reason is not None
            and task.allow_openai_fallback
            and self._openai_fallback_enabled
            and self._openai_api_token_configured
        )
        if should_fallback:
            estimated_cost = estimate_openai_request_cost(task.prompt, local_text)
            self._enforce_budget(estimated_cost)
            event = self._store.record_usage_event(
                provider="openai",
                model_name=self._openai_model,
                task_type=task.task_type,
                context_type=task.context_type,
                context_id=task.context_id,
                user_id=task.user_id,
                input_tokens=estimate_token_count(task.prompt),
                output_tokens=estimate_token_count(local_text),
                estimated_cost_usd=estimated_cost,
                cost_status=CostStatus.ESTIMATED.value,
                raw_usage={"fallback_reason": fallback_reason, "quality_score": local_quality},
            )
            return AiTaskResult(
                provider="openai",
                model_name=self._openai_model,
                task_type=task.task_type,
                output_text=local_text,
                quality_score=local_quality,
                fallback_used=True,
                fallback_reason=fallback_reason,
                estimated_cost_usd=estimated_cost,
                cost_status=CostStatus.ESTIMATED.value,
                usage_event_id=event.id,
            )

        event = self._store.record_usage_event(
            provider="ollama",
            model_name=self._local_model,
            task_type=task.task_type,
            context_type=task.context_type,
            context_id=task.context_id,
            user_id=task.user_id,
            input_tokens=estimate_token_count(task.prompt),
            output_tokens=estimate_token_count(local_text),
            estimated_cost_usd=Decimal("0"),
            cost_status=CostStatus.NOT_BILLABLE.value,
            raw_usage={"quality_score": local_quality, "fallback_reason": fallback_reason},
        )
        return AiTaskResult(
            provider="ollama",
            model_name=self._local_model,
            task_type=task.task_type,
            output_text=local_text,
            quality_score=local_quality,
            fallback_used=False,
            fallback_reason=fallback_reason,
            estimated_cost_usd=Decimal("0"),
            cost_status=CostStatus.NOT_BILLABLE.value,
            usage_event_id=event.id,
        )

    def _enforce_budget(self, estimated_cost: Decimal) -> None:
        if estimated_cost > self._single_request_budget_usd:
            raise BudgetExceededError("Estimated OpenAI fallback cost exceeds the single-request budget")
        now = datetime.now(UTC)
        month_start = self._month_start or datetime(now.year, now.month, 1, tzinfo=UTC)
        spent = self._store.sum_provider_estimated_cost("openai", month_start, now)
        if spent + estimated_cost > self._monthly_budget_usd:
            raise BudgetExceededError("Estimated OpenAI fallback cost exceeds the monthly budget")


def _local_response(prompt: str) -> str:
    trimmed = " ".join(prompt.split())
    if not trimmed:
        return ""
    return f"Local analysis: {trimmed[:500]}"


def score_local_quality(output_text: str, prompt: str) -> float:
    if not output_text.strip():
        return 0.0
    score = 0.45
    if len(output_text) >= 80:
        score += 0.2
    if any(word in output_text.lower() for word in ("compatible", "material", "printer", "model", "geometry")):
        score += 0.2
    if len(prompt.split()) >= 8:
        score += 0.1
    return min(score, 1.0)


def fallback_reason_for_quality(score: float, threshold: float) -> str | None:
    if score >= threshold:
        return None
    return "local_quality_below_threshold"


def estimate_token_count(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def estimate_openai_request_cost(prompt: str, output_text: str) -> Decimal:
    input_tokens = Decimal(estimate_token_count(prompt))
    output_tokens = Decimal(estimate_token_count(output_text))
    # Manual conservative default until pricing refresh/overrides are persisted.
    estimated = (input_tokens * Decimal("0.00000125")) + (output_tokens * Decimal("0.00001000"))
    return estimated.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


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
