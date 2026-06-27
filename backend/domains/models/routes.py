from __future__ import annotations

from dataclasses import dataclass
from gzip import BadGzipFile, decompress as gzip_decompress
from hashlib import sha256
from io import BytesIO
import json
from pathlib import PurePath
from urllib.parse import quote, urlparse
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.core.secrets import get_secret_cipher
from backend.domains.models.entities import GeometryParseError
from backend.domains.models.models import SourceProjectScan, SourceProjectScanFile
from backend.domains.models.schemas.response import (
    ModelResponse,
    SlicerArtifactResponse,
)
from backend.domains.models.responses import model_response, slicer_artifact_response
from backend.domains.models.service import MAX_UPLOAD_BYTES, SUPPORTED_EXTENSIONS, analyze_model_bytes, compress_model_payload, safe_filename
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
MAX_SOURCE_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_SLICER_ARTIFACT_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class DownloadedModelCandidate:
    filename: str
    content_type: str | None
    data: bytes
    source_project_url: str
    source_file_url: str


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
    scan_id: int | None = None
    site_key: str
    source_project_url: str
    external_project_id: str
    project_title: str | None
    scanned_at: str | None = None
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
    return [model_response(model) for model in store.list_models()]


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
    return model_response(model)


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
    return model_response(model)


@router.post("/imports/source-files/discover", response_model=SourceProjectFilesResponse)
def discover_source_model_files(
    request: DiscoverSourceFilesRequest,
    user=Depends(require_roles("user")),
    store: ModelStore = Depends(get_model_store),
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
    scan = store.save_source_project_scan(project_files, requested_by_user_id=getattr(user, "id", None))
    return _source_files_response(project_files, scan=scan)


@router.get("/imports/source-files/scans", response_model=list[SourceProjectFilesResponse])
def list_source_project_file_scans(
    limit: int = 20,
    _user=Depends(require_roles("viewer")),
    store: ModelStore = Depends(get_model_store),
) -> list[SourceProjectFilesResponse]:
    return [_source_files_response_from_scan(scan) for scan in store.list_source_project_scans(limit=max(1, min(limit, 100)))]


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
    downloaded_candidates: list[DownloadedModelCandidate] = []
    for file_id in request.file_ids:
        try:
            downloaded = runner.download_project_file(
                request.source_project_url,
                file_id,
                auth_headers=auth_headers,
                max_bytes=MAX_UPLOAD_BYTES,
            )
            downloaded_candidates.extend(_downloaded_model_candidates(downloaded))
        except SourceSiteRunnerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except GeometryParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    for candidate in downloaded_candidates:
        try:
            filename = safe_filename(candidate.filename)
            analysis = analyze_model_bytes(candidate.data, filename=filename, content_type=candidate.content_type)
            title = _downloaded_model_title(request.title, filename, len(downloaded_candidates))
            model = store.save_downloaded_model(
                title=title,
                source_project_url=_source_url(candidate.source_project_url, "source_project_url"),
                source_file_url=_source_url(candidate.source_file_url, "source_file_url"),
                filename=filename,
                content_type=candidate.content_type,
                analysis=analysis,
                payload=compress_model_payload(candidate.data),
                created_by_user_id=getattr(user, "id", None),
            )
        except GeometryParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        created_models.append(model_response(model))
    return created_models


@router.get("/{model_id}/files/{file_id}/slicer-artifacts", response_model=list[SlicerArtifactResponse])
def list_slicer_artifacts(
    model_id: int,
    file_id: int,
    _user=Depends(require_roles("viewer")),
    store: ModelStore = Depends(get_model_store),
) -> list[SlicerArtifactResponse]:
    if store.get_model_file(model_id, file_id) is None:
        raise HTTPException(status_code=404, detail="Model file not found")
    return [slicer_artifact_response(artifact) for artifact in store.list_slicer_artifacts(model_id, file_id)]


@router.post("/{model_id}/files/{file_id}/slicer-artifacts", response_model=SlicerArtifactResponse, status_code=201)
async def create_slicer_artifact(
    model_id: int,
    file_id: int,
    file: UploadFile = File(...),
    slicer_name: str = Form(...),
    output_format: str | None = Form(default=None),
    slicer_version: str | None = Form(default=None),
    printer_id: int | None = Form(default=None),
    profile_name: str | None = Form(default=None),
    settings_json: str = Form(default="{}"),
    user=Depends(require_roles("user")),
    store: ModelStore = Depends(get_model_store),
) -> SlicerArtifactResponse:
    data = await file.read(MAX_SLICER_ARTIFACT_BYTES + 1)
    if len(data) > MAX_SLICER_ARTIFACT_BYTES:
        raise HTTPException(status_code=413, detail=f"Slicer artifact exceeds the {MAX_SLICER_ARTIFACT_BYTES // (1024 * 1024)} MB import limit")
    clean_slicer_name = slicer_name.strip()[:120]
    if not clean_slicer_name:
        raise HTTPException(status_code=400, detail="Slicer name is required")
    filename = safe_filename(file.filename)
    settings = _parse_settings_json(settings_json)
    try:
        artifact = store.save_slicer_artifact(
            model_id=model_id,
            file_id=file_id,
            printer_id=printer_id,
            output_filename=filename,
            output_format=_artifact_output_format(filename, output_format),
            content_type=file.content_type,
            slicer_name=clean_slicer_name,
            slicer_version=(slicer_version or "").strip()[:80] or None,
            profile_name=(profile_name or "").strip()[:160] or None,
            settings=settings,
            settings_hash=_settings_hash(settings),
            payload=compress_model_payload(data),
            created_by_user_id=getattr(user, "id", None),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return slicer_artifact_response(artifact)


@router.get("/{model_id}/files/{file_id}/payload")
def restore_model_file_payload(
    model_id: int,
    file_id: int,
    _user=Depends(require_roles("viewer")),
    store: ModelStore = Depends(get_model_store),
) -> Response:
    model_file = store.get_model_file(model_id, file_id)
    if model_file is None:
        raise HTTPException(status_code=404, detail="Model file not found")
    payload = getattr(model_file, "payload", None)
    if payload is None:
        raise HTTPException(status_code=404, detail="Model file payload is not stored")
    if payload.compression != "gzip":
        raise HTTPException(status_code=409, detail="Stored model file payload uses an unsupported compression format")
    try:
        data = gzip_decompress(payload.compressed_bytes)
    except (BadGzipFile, OSError) as exc:
        raise HTTPException(status_code=409, detail="Stored model file payload could not be restored") from exc
    return Response(
        content=data,
        media_type=model_file.content_type or "application/octet-stream",
        headers=_download_headers(model_file.filename),
    )


@router.get("/{model_id}/files/{file_id}/slicer-artifacts/{artifact_id}/payload")
def restore_slicer_artifact_payload(
    model_id: int,
    file_id: int,
    artifact_id: int,
    _user=Depends(require_roles("viewer")),
    store: ModelStore = Depends(get_model_store),
) -> Response:
    artifact = store.get_slicer_artifact(model_id, file_id, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Slicer artifact not found")
    if artifact.compression != "gzip":
        raise HTTPException(status_code=409, detail="Stored slicer artifact uses an unsupported compression format")
    try:
        data = gzip_decompress(artifact.compressed_bytes)
    except (BadGzipFile, OSError) as exc:
        raise HTTPException(status_code=409, detail="Stored slicer artifact could not be restored") from exc
    return Response(
        content=data,
        media_type=artifact.content_type or "application/octet-stream",
        headers=_download_headers(artifact.output_filename),
    )


@router.get("/{model_id}", response_model=ModelResponse)
def get_model(
    model_id: int,
    _user=Depends(require_roles("viewer")),
    store: ModelStore = Depends(get_model_store),
) -> ModelResponse:
    model = store.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model_response(model)


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


def _source_files_response(project_files: SourceSiteProjectFiles, *, scan: SourceProjectScan | None = None) -> SourceProjectFilesResponse:
    return SourceProjectFilesResponse(
        scan_id=scan.id if scan is not None else None,
        site_key=project_files.site_key,
        source_project_url=project_files.source_project_url,
        external_project_id=project_files.external_project_id,
        project_title=project_files.project_title,
        scanned_at=scan.created_at.isoformat() if scan is not None else None,
        files=[_source_file_response(file) for file in project_files.files],
    )


def _source_files_response_from_scan(scan: SourceProjectScan) -> SourceProjectFilesResponse:
    return SourceProjectFilesResponse(
        scan_id=scan.id,
        site_key=scan.site_key,
        source_project_url=scan.source_project_url,
        external_project_id=scan.external_project_id,
        project_title=scan.project_title,
        scanned_at=scan.created_at.isoformat(),
        files=[_source_scan_file_response(file) for file in sorted(scan.files, key=lambda item: item.id)],
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


def _source_scan_file_response(file: SourceProjectScanFile) -> SourceModelFileResponse:
    return SourceModelFileResponse(
        file_id=file.file_id,
        filename=file.filename,
        file_format=file.file_format,
        size_bytes=file.size_bytes,
        source_file_url=file.source_file_url,
        supported_model_file=file.supported_model_file,
        created_at=file.source_created_at,
        notes=file.notes,
    )


def _downloaded_model_candidates(downloaded) -> list[DownloadedModelCandidate]:
    filename = safe_filename(downloaded.filename)
    if PurePath(filename).suffix.lower() != ".zip":
        return [
            DownloadedModelCandidate(
                filename=filename,
                content_type=downloaded.content_type,
                data=downloaded.data,
                source_project_url=downloaded.source_project_url,
                source_file_url=downloaded.source_file_url,
            )
        ]
    return _archive_model_candidates(downloaded)


def _archive_model_candidates(downloaded) -> list[DownloadedModelCandidate]:
    try:
        with ZipFile(BytesIO(downloaded.data)) as archive:
            return _archive_model_candidates_from_zip(downloaded, archive)
    except BadZipFile as exc:
        raise GeometryParseError("Downloaded archive is not a valid ZIP file.") from exc


def _archive_model_candidates_from_zip(downloaded, archive: ZipFile) -> list[DownloadedModelCandidate]:
    uncompressed_total = sum(item.file_size for item in archive.infolist())
    if uncompressed_total > MAX_SOURCE_ARCHIVE_UNCOMPRESSED_BYTES:
        raise GeometryParseError("Downloaded archive expands beyond the safe import limit.")
    candidates: list[DownloadedModelCandidate] = []
    for item in archive.infolist():
        if item.is_dir() or PurePath(item.filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        data = archive.read(item)
        if len(data) > MAX_UPLOAD_BYTES:
            raise GeometryParseError(f"Archived model file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB import limit.")
        candidates.append(
            DownloadedModelCandidate(
                filename=safe_filename(item.filename),
                content_type=_model_content_type(item.filename),
                data=data,
                source_project_url=downloaded.source_project_url,
                source_file_url=f"{downloaded.source_file_url}#{quote(item.filename)}",
            )
        )
    if not candidates:
        raise GeometryParseError("Downloaded archive does not contain STL or 3MF model files.")
    return candidates


def _model_content_type(filename: str) -> str | None:
    file_format = SUPPORTED_EXTENSIONS.get(PurePath(filename).suffix.lower())
    if file_format == "stl":
        return "model/stl"
    if file_format == "3mf":
        return "model/3mf"
    return None


def _download_headers(filename: str) -> dict[str, str]:
    safe_name = safe_filename(filename)
    ascii_name = safe_name.encode("ascii", errors="ignore").decode("ascii") or "model-file"
    ascii_name = ascii_name.replace('"', "").replace("\\", "")
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(safe_name)}"}


def _parse_settings_json(value: str) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Slicer settings must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Slicer settings must be a JSON object")
    return parsed


def _settings_hash(settings: dict) -> str:
    encoded = json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _artifact_output_format(filename: str, requested_format: str | None) -> str:
    raw_format = (requested_format or "").strip().lower()
    if raw_format:
        return raw_format[:40]
    return (PurePath(filename).suffix.lstrip(".").lower() or "unknown")[:40]


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
