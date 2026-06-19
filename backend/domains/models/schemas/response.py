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
    created_at: str


class ModelResponse(BaseModel):
    id: int
    title: str
    source_url: str | None
    status: str
    created_at: str
    updated_at: str
    files: list[ModelFileResponse] = Field(default_factory=list)
