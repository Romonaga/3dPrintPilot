from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.domains.models.entities import GeometryParseError
from backend.domains.models.models import Model, ModelFile
from backend.domains.models.schemas.response import ModelFilePayloadResponse, ModelFileResponse, ModelGeometryResponse, ModelResponse
from backend.domains.models.service import MAX_UPLOAD_BYTES, analyze_model_bytes, compress_model_payload, safe_filename
from backend.domains.models.store import ModelStore
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/models", tags=["models"])


def get_model_store(session: Session = Depends(get_db_session)) -> ModelStore:
    return ModelStore(session)


@router.get("", response_model=list[ModelResponse])
def list_models(
    _user=Depends(require_roles("viewer")),
    store: ModelStore = Depends(get_model_store),
) -> list[ModelResponse]:
    return [_model_response(model) for model in store.list_models()]


@router.post("/uploads", response_model=ModelResponse, status_code=201)
async def upload_model(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    user=Depends(require_roles("user")),
    store: ModelStore = Depends(get_model_store),
) -> ModelResponse:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Model file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit")
    filename = safe_filename(file.filename)
    try:
        analysis = analyze_model_bytes(data, filename=filename, content_type=file.content_type)
    except GeometryParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    model = store.save_uploaded_model(
        title=(title or filename).strip()[:240] or filename,
        source_url=(source_url or "").strip()[:2048] or None,
        filename=filename,
        content_type=file.content_type,
        size_bytes=len(data),
        analysis=analysis,
        created_by_user_id=getattr(user, "id", None),
    )
    return _model_response(model)


@router.post("/imports/downloaded-file", response_model=ModelResponse, status_code=201)
async def import_downloaded_model_file(
    file: UploadFile = File(...),
    source_project_url: str = Form(...),
    source_file_url: str = Form(...),
    title: str | None = Form(default=None),
    user=Depends(require_roles("user")),
    store: ModelStore = Depends(get_model_store),
) -> ModelResponse:
    project_url = _source_url(source_project_url, "source_project_url")
    file_url = _source_url(source_file_url, "source_file_url")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Model file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB import limit")
    filename = safe_filename(file.filename)
    try:
        analysis = analyze_model_bytes(data, filename=filename, content_type=file.content_type)
    except GeometryParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    model = store.save_downloaded_model(
        title=(title or filename).strip()[:240] or filename,
        source_project_url=project_url,
        source_file_url=file_url,
        filename=filename,
        content_type=file.content_type,
        analysis=analysis,
        payload=compress_model_payload(data),
        created_by_user_id=getattr(user, "id", None),
    )
    return _model_response(model)


@router.get("/{model_id}", response_model=ModelResponse)
def get_model(
    model_id: int,
    _user=Depends(require_roles("viewer")),
    store: ModelStore = Depends(get_model_store),
) -> ModelResponse:
    model = store.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return _model_response(model)


def _model_response(model: Model) -> ModelResponse:
    return ModelResponse(
        id=model.id,
        title=model.title,
        source_url=model.source_url,
        status=model.status,
        created_at=model.created_at.isoformat(),
        updated_at=model.updated_at.isoformat(),
        files=[_file_response(model_file) for model_file in model.files],
    )


def _file_response(model_file: ModelFile) -> ModelFileResponse:
    geometry = model_file.geometry
    payload = getattr(model_file, "payload", None)
    return ModelFileResponse(
        id=model_file.id,
        filename=model_file.filename,
        content_type=model_file.content_type,
        file_format=model_file.file_format,
        size_bytes=model_file.size_bytes,
        storage_status=model_file.storage_status,
        analysis_status=model_file.analysis_status,
        analysis_job_id=model_file.analysis_job_id,
        analysis_warnings=list(model_file.analysis_warnings or []),
        geometry=(
            ModelGeometryResponse(
                units=geometry.units,
                size_x_mm=geometry.size_x_mm,
                size_y_mm=geometry.size_y_mm,
                size_z_mm=geometry.size_z_mm,
                min_x_mm=geometry.min_x_mm,
                min_y_mm=geometry.min_y_mm,
                min_z_mm=geometry.min_z_mm,
                max_x_mm=geometry.max_x_mm,
                max_y_mm=geometry.max_y_mm,
                max_z_mm=geometry.max_z_mm,
                volume_mm3=geometry.volume_mm3,
                triangle_count=geometry.triangle_count,
                warnings=list(geometry.warnings or []),
            )
            if geometry is not None
            else None
        ),
        payload=(
            ModelFilePayloadResponse(
                source_project_url=payload.source_project_url,
                source_file_url=payload.source_file_url,
                compression=payload.compression,
                original_size_bytes=payload.original_size_bytes,
                compressed_size_bytes=payload.compressed_size_bytes,
                original_sha256=payload.original_sha256,
                compressed_sha256=payload.compressed_sha256,
                created_at=payload.created_at.isoformat(),
            )
            if payload is not None
            else None
        ),
        created_at=model_file.created_at.isoformat(),
    )


def _source_url(value: str, field_name: str) -> str:
    cleaned = value.strip()[:2048]
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be an absolute HTTP(S) URL")
    return cleaned
