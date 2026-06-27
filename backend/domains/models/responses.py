from __future__ import annotations

from backend.domains.models.models import Model, ModelFile, SlicerArtifact
from backend.domains.models.schemas.response import (
    ModelFilePayloadResponse,
    ModelFileResponse,
    ModelGeometryResponse,
    ModelResponse,
    SlicerArtifactResponse,
)


def model_response(model: Model) -> ModelResponse:
    return ModelResponse(
        id=model.id,
        title=model.title,
        source_url=model.source_url,
        status=model.status,
        created_at=model.created_at.isoformat(),
        updated_at=model.updated_at.isoformat(),
        files=[file_response(model_file) for model_file in model.files],
    )


def file_response(model_file: ModelFile) -> ModelFileResponse:
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


def slicer_artifact_response(artifact: SlicerArtifact) -> SlicerArtifactResponse:
    return SlicerArtifactResponse(
        id=artifact.id,
        model_file_id=artifact.model_file_id,
        printer_id=artifact.printer_id,
        output_filename=artifact.output_filename,
        output_format=artifact.output_format,
        content_type=artifact.content_type,
        slicer_name=artifact.slicer_name,
        slicer_version=artifact.slicer_version,
        profile_name=artifact.profile_name,
        settings=artifact.settings,
        settings_hash=artifact.settings_hash,
        status=artifact.status,
        compression=artifact.compression,
        original_size_bytes=artifact.original_size_bytes,
        compressed_size_bytes=artifact.compressed_size_bytes,
        original_sha256=artifact.original_sha256,
        compressed_sha256=artifact.compressed_sha256,
        created_at=artifact.created_at.isoformat(),
    )

