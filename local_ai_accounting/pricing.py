from __future__ import annotations

from decimal import Decimal

from local_ai_accounting.models import OpenAIPricingRate


def pricing_rate_from_mapping(row: dict) -> OpenAIPricingRate:
    return OpenAIPricingRate(
        model_name=str(row["model_name"]),
        input_per_1m_tokens=Decimal(str(row.get("input_per_1m_tokens") or row.get("input_per_million") or "0")),
        cached_input_per_1m_tokens=Decimal(
            str(row.get("cached_input_per_1m_tokens") or row.get("cached_input_per_million") or "0")
        ),
        output_per_1m_tokens=Decimal(str(row.get("output_per_1m_tokens") or row.get("output_per_million") or "0")),
        currency=str(row.get("currency") or "USD"),
    )

