from __future__ import annotations

from pydantic import BaseModel, Field


class ModelGeometryResponse(BaseModel):
    units: str
    size_x_mm: float | None
    size_y_mm: float | None
    size_z_mm: float | None
    min_x_mm: float | None
    min_y_mm: float | None
    min_z_mm: float | None
    max_x_mm: float | None
    max_y_mm: float | None
    max_z_mm: float | None
    volume_mm3: float | None
    triangle_count: int
    warnings: list[str] = Field(default_factory=list)


class ModelFilePayloadResponse(BaseModel):
    source_project_url: str
    source_file_url: str
    compression: str
    original_size_bytes: int
    compressed_size_bytes: int
    original_sha256: str
    compressed_sha256: str
    created_at: str


class ModelFileResponse(BaseModel):
    id: int
    filename: str
    content_type: str | None
    file_format: str
    size_bytes: int
    storage_status: str
    analysis_status: str
    analysis_job_id: int | None
    analysis_warnings: list[str] = Field(default_factory=list)
    geometry: ModelGeometryResponse | None = None
    payload: ModelFilePayloadResponse | None = None
    created_at: str


class SlicerArtifactResponse(BaseModel):
    id: int
    model_file_id: int
    printer_id: int | None
    output_filename: str
    output_format: str
    content_type: str | None
    slicer_name: str
    slicer_version: str | None
    profile_name: str | None
    settings: dict
    settings_hash: str
    status: str
    compression: str
    original_size_bytes: int
    compressed_size_bytes: int
    original_sha256: str
    compressed_sha256: str
    created_at: str


class ModelResponse(BaseModel):
    id: int
    title: str
    source_url: str | None
    status: str
    created_at: str
    updated_at: str
    files: list[ModelFileResponse] = Field(default_factory=list)
