from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.core.secrets import get_secret_cipher
from backend.domains.models.entities import GeometryParseError
from backend.domains.models.models import Model, ModelFile
from backend.domains.models.schemas.response import ModelFilePayloadResponse, ModelFileResponse, ModelGeometryResponse, ModelResponse
from backend.domains.models.service import MAX_UPLOAD_BYTES, analyze_model_bytes, compress_model_payload, safe_filename
from backend.domains.models.store import ModelStore
from backend.domains.site_scanning.runners import (
    SourceSiteCapability,
    SourceSiteFile,
    SourceSiteProjectFiles,
    SourceSiteRunner,
    SourceSiteRunnerError,
)
from backend.domains.site_scanning.service import SiteScanService
from backend.domains.site_scanning.store import SiteAuthProfileStore
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/models", tags=["models"])
source_site_service = SiteScanService()


class DiscoverSourceFilesRequest(BaseModel):
    source_project_url: str = Field(..., min_length=8, max_length=2048)
    site_key: str = Field(default="printables", min_length=1, max_length=80)


class ImportSourceFilesRequest(BaseModel):
    source_project_url: str = Field(..., min_length=8, max_length=2048)
    site_key: str = Field(default="printables", min_length=1, max_length=80)
    file_ids: list[str] = Field(..., min_length=1, max_length=10)
    title: str | None = Field(default=None, max_length=240)


class SourceModelFileResponse(BaseModel):
    file_id: str
    filename: str
    file_format: str
    size_bytes: int | None
    source_file_url: str
    supported_model_file: bool
    created_at: str | None
    notes: str | None


class SourceProjectFilesResponse(BaseModel):
    site_key: str
    source_project_url: str
    external_project_id: str
    project_title: str | None
    files: list[SourceModelFileResponse]


def get_model_store(session: Session = Depends(get_db_session)) -> ModelStore:
    return ModelStore(session)


def get_site_auth_profile_store(session: Session = Depends(get_db_session)) -> SiteAuthProfileStore:
    return SiteAuthProfileStore(session, get_secret_cipher())


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


@router.post("/imports/source-files/discover", response_model=SourceProjectFilesResponse)
def discover_source_model_files(
    request: DiscoverSourceFilesRequest,
    _user=Depends(require_roles("user")),
    auth_store: SiteAuthProfileStore = Depends(get_site_auth_profile_store),
) -> SourceProjectFilesResponse:
    runner = _source_site_runner(request.site_key, SourceSiteCapability.FILE_LISTING)
    try:
        project_files = runner.list_project_files(
            request.source_project_url,
            auth_headers=_source_auth_headers(auth_store, request.site_key),
        )
    except SourceSiteRunnerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_files_response(project_files)


@router.post("/imports/source-files", response_model=list[ModelResponse], status_code=201)
def import_source_model_files(
    request: ImportSourceFilesRequest,
    user=Depends(require_roles("user")),
    store: ModelStore = Depends(get_model_store),
    auth_store: SiteAuthProfileStore = Depends(get_site_auth_profile_store),
) -> list[ModelResponse]:
    runner = _source_site_runner(request.site_key, SourceSiteCapability.FILE_DOWNLOAD)
    auth_headers = _source_auth_headers(auth_store, request.site_key)
    created_models: list[ModelResponse] = []
    for file_id in request.file_ids:
        try:
            downloaded = runner.download_project_file(
                request.source_project_url,
                file_id,
                auth_headers=auth_headers,
                max_bytes=MAX_UPLOAD_BYTES,
            )
            filename = safe_filename(downloaded.filename)
            analysis = analyze_model_bytes(downloaded.data, filename=filename, content_type=downloaded.content_type)
            title = _downloaded_model_title(request.title, filename, len(request.file_ids))
            model = store.save_downloaded_model(
                title=title,
                source_project_url=_source_url(downloaded.source_project_url, "source_project_url"),
                source_file_url=_source_url(downloaded.source_file_url, "source_file_url"),
                filename=filename,
                content_type=downloaded.content_type,
                analysis=analysis,
                payload=compress_model_payload(downloaded.data),
                created_by_user_id=getattr(user, "id", None),
            )
        except SourceSiteRunnerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except GeometryParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        created_models.append(_model_response(model))
    return created_models


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


def _source_site_runner(site_key: str, capability: SourceSiteCapability) -> SourceSiteRunner:
    normalized_site_key = site_key.strip().lower()
    runner = source_site_service.runner_for(normalized_site_key)
    if runner is None:
        raise HTTPException(status_code=404, detail="Source site runner not found")
    if capability not in runner.manifest.capabilities:
        raise HTTPException(status_code=400, detail=f"Source site does not support {capability.value}")
    return runner


def _source_auth_headers(auth_store: SiteAuthProfileStore, site_key: str) -> dict[str, str] | None:
    try:
        context = auth_store.auth_context_for_site(site_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return context.headers if context.enabled and context.headers else None


def _source_files_response(project_files: SourceSiteProjectFiles) -> SourceProjectFilesResponse:
    return SourceProjectFilesResponse(
        site_key=project_files.site_key,
        source_project_url=project_files.source_project_url,
        external_project_id=project_files.external_project_id,
        project_title=project_files.project_title,
        files=[_source_file_response(file) for file in project_files.files],
    )


def _source_file_response(file: SourceSiteFile) -> SourceModelFileResponse:
    return SourceModelFileResponse(
        file_id=file.file_id,
        filename=file.filename,
        file_format=file.file_format,
        size_bytes=file.size_bytes,
        source_file_url=file.source_file_url,
        supported_model_file=file.supported_model_file,
        created_at=file.created_at,
        notes=file.notes,
    )


def _downloaded_model_title(title: str | None, filename: str, selected_count: int) -> str:
    clean_title = (title or "").strip()[:240]
    if selected_count == 1 and clean_title:
        return clean_title
    return filename


def _source_url(value: str, field_name: str) -> str:
    cleaned = value.strip()[:2048]
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be an absolute HTTP(S) URL")
    return cleaned
