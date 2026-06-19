from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.domains.models.entities import GeometryParseError
from backend.domains.models.routes import get_model_store
from backend.domains.models.service import MAX_UPLOAD_BYTES, analyze_model_bytes
from tests.helpers import allow_anonymous_until_bootstrap


ASCII_STL = b"""solid sample
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 10 0 0
    vertex 0 20 0
  endloop
endfacet
endsolid sample
"""


class FakeModelStore:
    def __init__(self) -> None:
        self.saved = []

    def list_models(self, limit=50):
        return []

    def get_model(self, model_id):
        return None

    def save_uploaded_model(self, **kwargs):
        self.saved.append(kwargs)
        now = datetime.now(UTC)
        analysis = kwargs["analysis"]
        geometry = SimpleNamespace(
            units=analysis.units,
            size_x_mm=analysis.size_x_mm,
            size_y_mm=analysis.size_y_mm,
            size_z_mm=analysis.size_z_mm,
            min_x_mm=analysis.min_x_mm,
            min_y_mm=analysis.min_y_mm,
            min_z_mm=analysis.min_z_mm,
            max_x_mm=analysis.max_x_mm,
            max_y_mm=analysis.max_y_mm,
            max_z_mm=analysis.max_z_mm,
            volume_mm3=analysis.volume_mm3,
            triangle_count=analysis.triangle_count,
            warnings=list(analysis.warnings),
        )
        model_file = SimpleNamespace(
            id=7,
            filename=kwargs["filename"],
            content_type=kwargs["content_type"],
            file_format=analysis.file_format,
            size_bytes=kwargs["size_bytes"],
            storage_status="metadata_only",
            analysis_status="completed",
            analysis_job_id=42,
            analysis_warnings=list(analysis.warnings),
            geometry=geometry,
            created_at=now,
        )
        return SimpleNamespace(
            id=3,
            title=kwargs["title"],
            source_url=kwargs["source_url"],
            status="analyzed",
            created_at=now,
            updated_at=now,
            files=[model_file],
        )


def test_ascii_stl_analysis_extracts_bounds_and_warning_for_flat_volume():
    analysis = analyze_model_bytes(ASCII_STL, filename="sample.stl", content_type="model/stl")

    assert analysis.file_format == "stl"
    assert analysis.triangle_count == 1
    assert analysis.size_x_mm == 10
    assert analysis.size_y_mm == 20
    assert analysis.size_z_mm == 0
    assert "Model volume is zero" in analysis.warnings[0]


def test_3mf_analysis_extracts_mesh_geometry():
    analysis = analyze_model_bytes(_sample_3mf(), filename="part.3mf")

    assert analysis.file_format == "3mf"
    assert analysis.triangle_count == 1
    assert analysis.size_x_mm == 10
    assert analysis.size_y_mm == 20
    assert analysis.units == "millimeter"


def test_malformed_model_fails_safely():
    try:
        analyze_model_bytes(b"not a model", filename="broken.stl")
    except GeometryParseError as exc:
        assert "STL file does not contain" in str(exc)
    else:
        raise AssertionError("Expected GeometryParseError")


def test_model_upload_endpoint_persists_geometry_and_source_metadata():
    store = FakeModelStore()
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: store
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post(
        "/api/models/uploads",
        data={"title": "Calibration Triangle", "source_url": "https://models.example/triangle"},
        files={"file": ("../unsafe-name.stl", ASCII_STL, "model/stl")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Calibration Triangle"
    assert body["source_url"] == "https://models.example/triangle"
    assert body["files"][0]["filename"] == "unsafe-name.stl"
    assert body["files"][0]["analysis_job_id"] == 42
    assert body["files"][0]["geometry"]["triangle_count"] == 1
    assert store.saved[0]["created_by_user_id"] is None


def test_model_upload_rejects_oversized_files_before_parsing():
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: FakeModelStore()
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post(
        "/api/models/uploads",
        files={"file": ("huge.stl", b"0" * (MAX_UPLOAD_BYTES + 1), "model/stl")},
    )

    assert response.status_code == 413


def _sample_3mf() -> bytes:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <object id="1" type="model">
      <mesh>
        <vertices>
          <vertex x="0" y="0" z="0" />
          <vertex x="10" y="0" z="0" />
          <vertex x="0" y="20" z="0" />
        </vertices>
        <triangles>
          <triangle v1="0" v2="1" v3="2" />
        </triangles>
      </mesh>
    </object>
  </resources>
  <build><item objectid="1" /></build>
</model>
"""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model", xml)
    return buffer.getvalue()
