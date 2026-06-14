from __future__ import annotations

from fastapi import APIRouter

from backend.core.config import get_settings
from backend.domains.health.schemas.response import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
    )

