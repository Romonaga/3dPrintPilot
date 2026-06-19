from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.domains.resources.schemas.response import ResourceStatusResponse
from backend.domains.resources.service import build_resource_status
from backend.domains.resources.store import ResourceStore
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("/status", response_model=ResourceStatusResponse)
def resource_status(_user=Depends(require_roles("viewer"))) -> ResourceStatusResponse:
    return ResourceStatusResponse.model_validate(build_resource_status())


@router.post("/samples", status_code=201)
def record_resource_sample(
    _user=Depends(require_roles("admin")),
    session: Session = Depends(get_db_session),
) -> dict[str, int]:
    sample = ResourceStore(session).save_sample(build_resource_status())
    return {"id": sample.id}


@router.get("/jobs")
def list_background_jobs(
    limit: int = 25,
    _user=Depends(require_roles("admin")),
    session: Session = Depends(get_db_session),
) -> list[dict]:
    jobs = ResourceStore(session).list_jobs(limit)
    return [
        {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "priority": job.priority,
            "attempts": job.attempts,
            "created_at": job.created_at.isoformat(),
        }
        for job in jobs
    ]
