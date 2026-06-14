from __future__ import annotations

from fastapi import APIRouter

from backend.domains.resources.schemas.response import ResourceStatusResponse
from backend.domains.resources.service import build_resource_status

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("/status", response_model=ResourceStatusResponse)
def resource_status() -> ResourceStatusResponse:
    return ResourceStatusResponse.model_validate(build_resource_status())

