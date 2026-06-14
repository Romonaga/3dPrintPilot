from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from local_ai_accounting.models import OpenAIPricingRate, TokenUsage

MONEY_QUANT = Decimal("0.00000001")


def normalize_openai_usage(raw_usage: dict[str, Any] | None) -> TokenUsage:
    usage = raw_usage or {}
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    return TokenUsage(
        input_tokens=_int_value(usage.get("input_tokens")),
        cached_input_tokens=_int_value(input_details.get("cached_tokens") or usage.get("input_cached_tokens")),
        output_tokens=_int_value(usage.get("output_tokens")),
        reasoning_tokens=_int_value(output_details.get("reasoning_tokens")),
        total_tokens=_int_value(usage.get("total_tokens")),
    )


def estimate_openai_cost(
    usage: TokenUsage,
    pricing: OpenAIPricingRate,
    *,
    tool_call_cost_usd: Decimal | str | float | int = Decimal("0"),
) -> Decimal:
    regular_input_tokens = max(0, usage.input_tokens - usage.cached_input_tokens)
    raw_cost = (
        Decimal(regular_input_tokens) * pricing.input_per_1m_tokens
        + Decimal(usage.cached_input_tokens) * pricing.cached_input_per_1m_tokens
        + Decimal(usage.output_tokens) * pricing.output_per_1m_tokens
    ) / Decimal(1_000_000)
    raw_cost += Decimal(str(tool_call_cost_usd or "0"))
    return raw_cost.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _int_value(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0

