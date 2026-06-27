from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from local_ai_accounting import (
    CostStatus,
    OpenAIPricingRate,
    TokenUsage,
    UsageCostEvent,
    estimate_openai_cost,
    normalize_openai_usage,
    reconcile_cost_bucket,
)
from backend.domains.ai.service import OpenAICostReconciliationService, extract_openai_cost_total_usd
from backend.domains.ai.service import AiTaskInput, AiTaskRunner, BudgetExceededError, fallback_reason_for_quality


def test_estimate_openai_cost_separates_cached_input_tokens():
    usage = TokenUsage(input_tokens=1000, cached_input_tokens=250, output_tokens=500)
    pricing = OpenAIPricingRate(
        model_name="example",
        input_per_1m_tokens=Decimal("2.50"),
        cached_input_per_1m_tokens=Decimal("0.25"),
        output_per_1m_tokens=Decimal("15.00"),
    )

    cost = estimate_openai_cost(usage, pricing)

    assert cost == Decimal("0.00943750")


def test_normalize_openai_usage_reads_responses_api_shape():
    usage = normalize_openai_usage(
        {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens": 12},
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 4},
            "total_tokens": 120,
        }
    )

    assert usage.input_tokens == 100
    assert usage.cached_input_tokens == 12
    assert usage.output_tokens == 20
    assert usage.reasoning_tokens == 4
    assert usage.total_tokens == 120


def test_reconcile_cost_bucket_allocates_final_cost_proportionally():
    now = datetime.now(timezone.utc)
    events = [
        UsageCostEvent(
            event_id="a",
            created_at=now,
            provider="openai",
            model_name="example",
            usage=TokenUsage(input_tokens=100),
            estimated_cost_usd=Decimal("0.30"),
        ),
        UsageCostEvent(
            event_id="b",
            created_at=now,
            provider="openai",
            model_name="example",
            usage=TokenUsage(input_tokens=300),
            estimated_cost_usd=Decimal("0.70"),
        ),
    ]

    updates = reconcile_cost_bucket(events, verified_cost_usd=Decimal("1.20"), reconciliation_run_id="run-1")

    assert [update.event_id for update in updates] == ["a", "b"]
    assert updates[0].final_cost_usd == Decimal("0.36000000")
    assert updates[1].final_cost_usd == Decimal("0.84000000")
    assert updates[0].cost_status == CostStatus.ADJUSTED
    assert updates[0].reconciliation_run_id == "run-1"


def test_reconcile_ignores_local_ollama_events():
    now = datetime.now(timezone.utc)
    events = [
        UsageCostEvent(
            event_id="local",
            created_at=now,
            provider="ollama",
            model_name="qwen",
            usage=TokenUsage(input_tokens=100),
            estimated_cost_usd=Decimal("0"),
            cost_status=CostStatus.NOT_BILLABLE,
        )
    ]

    assert reconcile_cost_bucket(events, verified_cost_usd=Decimal("1.20")) == []


def test_extract_openai_cost_total_usd_reads_cost_buckets():
    buckets = [
        {
            "start_time": 1730419200,
            "end_time": 1730505600,
            "results": [
                {"amount": {"value": 0.06, "currency": "usd"}},
                {"amount": {"value": "0.04", "currency": "usd"}},
                {"amount": {"value": "2.00", "currency": "eur"}},
            ],
        }
    ]

    assert extract_openai_cost_total_usd(buckets) == Decimal("0.10000000")


def test_openai_cost_reconciliation_service_fetches_costs_and_updates_events():
    now = datetime(2026, 6, 14, tzinfo=timezone.utc)
    store = FakeAiAccountingStore(
        [
            UsageCostEvent(
                event_id="1",
                created_at=now,
                provider="openai",
                model_name="gpt-test",
                usage=TokenUsage(input_tokens=100),
                estimated_cost_usd=Decimal("0.25"),
            ),
            UsageCostEvent(
                event_id="2",
                created_at=now,
                provider="openai",
                model_name="gpt-test",
                usage=TokenUsage(input_tokens=300),
                estimated_cost_usd=Decimal("0.75"),
            ),
        ]
    )
    client = FakeOpenAICostClient(
        {
            "data": [
                {
                    "start_time": 1781395200,
                    "end_time": 1781481600,
                    "results": [{"amount": {"value": "1.20", "currency": "usd"}}],
                }
            ]
        }
    )
    service = OpenAICostReconciliationService(store, client)

    result = service.reconcile_period(
        period_start=datetime(2026, 6, 14, tzinfo=timezone.utc),
        period_end=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )

    assert result.status == "completed"
    assert result.final_total_usd == Decimal("1.20000000")
    assert result.event_count == 2
    assert result.updated_event_count == 2
    assert client.requested_params["bucket_width"] == "1d"
    assert [update.final_cost_usd for update in store.updates] == [Decimal("0.30000000"), Decimal("0.90000000")]
    assert store.completed["status"] == "completed"


def test_openai_cost_reconciliation_service_records_failed_run_before_reraising():
    now = datetime(2026, 6, 14, tzinfo=timezone.utc)
    store = FakeAiAccountingStore([])
    service = OpenAICostReconciliationService(store, FailingOpenAICostClient())

    with pytest.raises(RuntimeError, match="cost service unavailable"):
        service.reconcile_period(
            period_start=now,
            period_end=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )

    assert store.created["run_id"]
    assert store.completed["run_id"] == store.created["run_id"]
    assert store.completed["status"] == "failed"
    assert store.completed["final_total_usd"] is None
    assert store.completed["details"]["error"] == "cost service unavailable"


def test_ai_task_runner_records_local_ollama_usage_when_fallback_disabled():
    store = FakeAiTaskStore()
    runner = AiTaskRunner(
        store=store,
        local_model="qwen3",
        openai_model="gpt-5.4",
        quality_threshold=0.99,
        openai_fallback_enabled=False,
        openai_api_token_configured=False,
        monthly_budget_usd=Decimal("5.00"),
        single_request_budget_usd=Decimal("0.25"),
    )

    result = runner.run(AiTaskInput(task_type="compatibility_explanation", prompt="Explain model printer material compatibility."))

    assert result.provider == "ollama"
    assert result.fallback_used is False
    assert result.estimated_cost_usd == Decimal("0")
    assert store.events[0]["provider"] == "ollama"
    assert store.events[0]["cost_status"] == "not_billable"


def test_ai_task_runner_uses_openai_fallback_only_when_enabled_and_budget_allows():
    store = FakeAiTaskStore()
    runner = AiTaskRunner(
        store=store,
        local_model="qwen3",
        openai_model="gpt-5.4",
        quality_threshold=0.99,
        openai_fallback_enabled=True,
        openai_api_token_configured=True,
        monthly_budget_usd=Decimal("5.00"),
        single_request_budget_usd=Decimal("0.25"),
    )

    result = runner.run(
        AiTaskInput(
            task_type="requirement_extraction",
            prompt="x",
            allow_openai_fallback=True,
        )
    )

    assert result.provider == "openai"
    assert result.fallback_used is True
    assert result.fallback_reason == "local_quality_below_threshold"
    assert result.estimated_cost_usd > Decimal("0")
    assert store.events[0]["provider"] == "openai"
    assert store.events[0]["cost_status"] == "estimated"


def test_ai_task_runner_blocks_openai_fallback_when_request_budget_would_be_exceeded():
    store = FakeAiTaskStore()
    runner = AiTaskRunner(
        store=store,
        local_model="qwen3",
        openai_model="gpt-5.4",
        quality_threshold=0.99,
        openai_fallback_enabled=True,
        openai_api_token_configured=True,
        monthly_budget_usd=Decimal("5.00"),
        single_request_budget_usd=Decimal("0.00000001"),
    )

    try:
        runner.run(AiTaskInput(task_type="expensive", prompt="x", allow_openai_fallback=True))
    except BudgetExceededError as exc:
        assert "single-request budget" in str(exc)
    else:
        raise AssertionError("Expected BudgetExceededError")

    assert store.events == []


def test_fallback_reason_is_none_when_quality_meets_threshold():
    assert fallback_reason_for_quality(0.8, 0.72) is None
    assert fallback_reason_for_quality(0.5, 0.72) == "local_quality_below_threshold"


class FakeOpenAICostClient:
    def __init__(self, payload):
        self.payload = payload
        self.requested_params = {}

    def fetch_costs(self, **kwargs):
        self.requested_params = kwargs
        return self.payload


class FailingOpenAICostClient:
    def fetch_costs(self, **kwargs):
        raise RuntimeError("cost service unavailable")


class FakeAiAccountingStore:
    def __init__(self, events):
        self.events = events
        self.created = {}
        self.completed = {}
        self.updates = []

    def list_reconcilable_events(self, start, end):
        return self.events

    def create_reconciliation_run(self, **kwargs):
        self.created = kwargs

    def apply_event_updates(self, updates):
        self.updates = updates

    def complete_reconciliation_run(self, run_id, **kwargs):
        self.completed = {"run_id": run_id, **kwargs}


class FakeAiTaskStore:
    def __init__(self):
        self.events = []
        self.next_id = 1

    def sum_provider_estimated_cost(self, provider, start, end):
        return Decimal("0")

    def record_usage_event(self, **kwargs):
        self.events.append(kwargs)
        event = type("Event", (), {"id": self.next_id})()
        self.next_id += 1
        return event
