from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class OpenAIAdminClient:
    admin_api_key: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 30

    def fetch_costs(
        self,
        *,
        start_time: int,
        end_time: int | None = None,
        bucket_width: str = "1d",
        group_by: list[str] | None = None,
        limit: int = 180,
    ) -> dict[str, Any]:
        return self._get_paginated(
            "/organization/costs",
            {
                "start_time": start_time,
                "end_time": end_time,
                "bucket_width": bucket_width,
                "group_by": group_by,
                "limit": limit,
            },
        )

    def fetch_completions_usage(
        self,
        *,
        start_time: int,
        end_time: int | None = None,
        group_by: list[str] | None = None,
        models: list[str] | None = None,
        limit: int = 31,
    ) -> dict[str, Any]:
        return self._get_paginated(
            "/organization/usage/completions",
            {
                "start_time": start_time,
                "end_time": end_time,
                "group_by": group_by,
                "models": models,
                "limit": limit,
            },
        )

    def _get_paginated(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        clean_params = {key: value for key, value in params.items() if value not in (None, [], "")}
        headers = {"Authorization": f"Bearer {self.admin_api_key}", "Content-Type": "application/json"}
        buckets: list[dict[str, Any]] = []
        page: str | None = None
        with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds, headers=headers) as client:
            while True:
                request_params = dict(clean_params)
                if page:
                    request_params["page"] = page
                response = client.get(path, params=request_params)
                response.raise_for_status()
                payload = response.json()
                buckets.extend(payload.get("data") or [])
                page = payload.get("next_page")
                if not payload.get("has_more") or not page:
                    return {"object": "page", "data": buckets, "has_more": False, "next_page": None}
