from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GeometryAnalysis:
    file_format: str
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
    warnings: tuple[str, ...] = field(default_factory=tuple)


class GeometryParseError(ValueError):
    """Raised when a model file cannot be safely parsed."""


@dataclass(frozen=True)
class CompressedModelPayload:
    compression: str
    compressed_bytes: bytes
    original_size_bytes: int
    compressed_size_bytes: int
    original_sha256: str
    compressed_sha256: str
