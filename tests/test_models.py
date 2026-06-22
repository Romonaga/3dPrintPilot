from __future__ import annotations

from datetime import UTC, datetime
from gzip import decompress as gzip_decompress
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.domains.models.entities import GeometryParseError
import backend.domains.models.routes as model_routes
from backend.domains.models.routes import get_model_store, get_site_auth_profile_store
from backend.domains.models.service import MAX_UPLOAD_BYTES, analyze_model_bytes, compress_model_payload
from backend.domains.site_scanning.runners import (
    SourceSiteCapability,
    SourceSiteDownloadedFile,
    SourceSiteFile,
    SourceSiteProjectFiles,
    SourceSiteRunnerManifest,
    SourceSiteSupportLevel,
)
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
        self.source_scans = []

    def list_source_project_scans(self, limit=20):
        return self.source_scans[:limit]

    def save_source_project_scan(self, project_files, *, requested_by_user_id):
        now = datetime.now(UTC)
        scan = SimpleNamespace(
            id=11 + len(self.source_scans),
            site_key=project_files.site_key,
            source_project_url=project_files.source_project_url,
            external_project_id=project_files.external_project_id,
            project_title=project_files.project_title,
            requested_by_user_id=requested_by_user_id,
            raw_metadata={"file_count": len(project_files.files)},
            created_at=now,
            updated_at=now,
            files=[
                SimpleNamespace(
                    id=index + 1,
                    file_id=source_file.file_id,
                    filename=source_file.filename,
                    file_format=source_file.file_format,
                    size_bytes=source_file.size_bytes,
                    source_file_url=source_file.source_file_url,
                    supported_model_file=source_file.supported_model_file,
                    source_created_at=source_file.created_at,
                    notes=source_file.notes,
                    raw_metadata={},
                    created_at=now,
                )
                for index, source_file in enumerate(project_files.files)
            ],
        )
        self.source_scans.insert(0, scan)
        return scan

    def list_models(self, limit=50):
        return []

    def get_model(self, model_id):
        return None

    def save_uploaded_model(self, **kwargs):
        self.saved.append(kwargs)
        now = datetime.now(UTC)
        analysis = kwargs["analysis"]
        payload = kwargs.get("payload")
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
            payload=payload,
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

    def save_downloaded_model(self, **kwargs):
        self.saved.append(kwargs)
        now = datetime.now(UTC)
        analysis = kwargs["analysis"]
        compressed_payload = kwargs["payload"]
        payload = SimpleNamespace(
            source_project_url=kwargs["source_project_url"],
            source_file_url=kwargs["source_file_url"],
            compression=compressed_payload.compression,
            original_size_bytes=compressed_payload.original_size_bytes,
            compressed_size_bytes=compressed_payload.compressed_size_bytes,
            original_sha256=compressed_payload.original_sha256,
            compressed_sha256=compressed_payload.compressed_sha256,
            created_at=now,
        )
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
            id=8,
            filename=kwargs["filename"],
            content_type=kwargs["content_type"],
            file_format=analysis.file_format,
            size_bytes=compressed_payload.original_size_bytes,
            storage_status="stored_compressed",
            analysis_status="completed",
            analysis_job_id=43,
            analysis_warnings=list(analysis.warnings),
            geometry=geometry,
            payload=payload,
            created_at=now,
        )
        return SimpleNamespace(
            id=4,
            title=kwargs["title"],
            source_url=kwargs["source_project_url"],
            status="analyzed",
            created_at=now,
            updated_at=now,
            files=[model_file],
        )


class FakeSourceAuthStore:
    def __init__(self) -> None:
        self.requested_site_keys = []

    def auth_context_for_site(self, site_key):
        self.requested_site_keys.append(site_key)
        return SimpleNamespace(enabled=True, headers={"Cookie": "session=abc"})


class FakeSourceRunner:
    manifest = SourceSiteRunnerManifest(
        site_key="printables",
        display_name="Printables",
        support_level=SourceSiteSupportLevel.PARTIAL,
        capabilities=(SourceSiteCapability.FILE_LISTING, SourceSiteCapability.FILE_DOWNLOAD),
        allowed_hosts=("printables.com", "www.printables.com"),
    )

    def __init__(self) -> None:
        self.list_headers = []
        self.download_headers = []

    def identify_project(self, url):
        return None

    def list_project_files(self, project_url, *, auth_headers=None):
        self.list_headers.append(auth_headers)
        return SourceSiteProjectFiles(
            site_key="printables",
            source_project_url="https://www.printables.com/model/123-triangle",
            external_project_id="123",
            project_title="Triangle",
            files=(
                SourceSiteFile(
                    file_id="stl-1",
                    filename="triangle.stl",
                    file_format="stl",
                    size_bytes=len(ASCII_STL),
                    source_file_url="https://www.printables.com/model/123-triangle/files#file-stl-1",
                    supported_model_file=True,
                ),
                SourceSiteFile(
                    file_id="scad-1",
                    filename="triangle.scad",
                    file_format="scad",
                    size_bytes=100,
                    source_file_url="https://www.printables.com/model/123-triangle/files#file-scad-1",
                    supported_model_file=False,
                ),
            ),
        )

    def download_project_file(self, project_url, file_id, *, auth_headers=None, max_bytes):
        self.download_headers.append(auth_headers)
        assert project_url == "https://www.printables.com/model/123-triangle"
        assert file_id == "stl-1"
        assert max_bytes == MAX_UPLOAD_BYTES
        return SourceSiteDownloadedFile(
            file_id=file_id,
            filename="../triangle.stl",
            content_type="model/stl",
            data=ASCII_STL,
            source_project_url="https://www.printables.com/model/123-triangle",
            source_file_url="https://files.printables.com/media/prints/123/triangle.stl",
        )


class FakeSourceSiteService:
    def __init__(self, runner: FakeSourceRunner) -> None:
        self.runner = runner

    def runner_for(self, site_key: str):
        return self.runner if site_key == "printables" else None


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


def test_model_import_downloaded_file_stores_compressed_payload_metadata_without_returning_bytes():
    store = FakeModelStore()
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: store
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post(
        "/api/models/imports/downloaded-file",
        data={
            "title": "Downloaded Triangle",
            "source_project_url": "https://models.example/projects/triangle",
            "source_file_url": "https://cdn.models.example/files/triangle.stl",
        },
        files={"file": ("../unsafe-name.stl", ASCII_STL, "model/stl")},
    )

    assert response.status_code == 201
    body = response.json()
    payload = body["files"][0]["payload"]
    assert body["source_url"] == "https://models.example/projects/triangle"
    assert body["files"][0]["storage_status"] == "stored_compressed"
    assert payload["source_project_url"] == "https://models.example/projects/triangle"
    assert payload["source_file_url"] == "https://cdn.models.example/files/triangle.stl"
    assert payload["compression"] == "gzip"
    assert payload["original_size_bytes"] == len(ASCII_STL)
    assert payload["original_sha256"] == sha256(ASCII_STL).hexdigest()
    assert "compressed_bytes" not in response.text
    stored_payload = store.saved[0]["payload"]
    assert gzip_decompress(stored_payload.compressed_bytes) == ASCII_STL
    assert store.saved[0]["filename"] == "unsafe-name.stl"


def test_model_import_downloaded_file_requires_absolute_source_urls():
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: FakeModelStore()
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post(
        "/api/models/imports/downloaded-file",
        data={"source_project_url": "/local/project", "source_file_url": "https://cdn.models.example/files/triangle.stl"},
        files={"file": ("triangle.stl", ASCII_STL, "model/stl")},
    )

    assert response.status_code == 400


def test_model_source_file_discovery_returns_printables_files_without_auth_values(monkeypatch):
    store = FakeModelStore()
    runner = FakeSourceRunner()
    auth_store = FakeSourceAuthStore()
    monkeypatch.setattr(model_routes, "source_site_service", FakeSourceSiteService(runner))
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: store
    app.dependency_overrides[get_site_auth_profile_store] = lambda: auth_store
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post(
        "/api/models/imports/source-files/discover",
        json={"site_key": "printables", "source_project_url": "https://www.printables.com/model/123-triangle"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scan_id"] == 11
    assert body["scanned_at"] is not None
    assert body["project_title"] == "Triangle"
    assert body["files"][0]["filename"] == "triangle.stl"
    assert body["files"][0]["supported_model_file"] is True
    assert body["files"][1]["supported_model_file"] is False
    assert store.source_scans[0].source_project_url == "https://www.printables.com/model/123-triangle"
    assert runner.list_headers == [{"Cookie": "session=abc"}]
    assert "session=abc" not in response.text


def test_model_source_file_scan_list_returns_saved_project_files():
    store = FakeModelStore()
    project_files = FakeSourceRunner().list_project_files("https://www.printables.com/model/123-triangle")
    store.save_source_project_scan(project_files, requested_by_user_id=None)
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: store
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.get("/api/models/imports/source-files/scans")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["site_key"] == "printables"
    assert body[0]["project_title"] == "Triangle"
    assert body[0]["files"][0]["file_id"] == "stl-1"
    assert body[0]["files"][1]["supported_model_file"] is False


def test_model_source_file_import_downloads_and_stores_selected_printables_files(monkeypatch):
    store = FakeModelStore()
    runner = FakeSourceRunner()
    auth_store = FakeSourceAuthStore()
    monkeypatch.setattr(model_routes, "source_site_service", FakeSourceSiteService(runner))
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: store
    app.dependency_overrides[get_site_auth_profile_store] = lambda: auth_store
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post(
        "/api/models/imports/source-files",
        json={
            "site_key": "printables",
            "source_project_url": "https://www.printables.com/model/123-triangle",
            "file_ids": ["stl-1"],
            "title": "Managed Triangle",
        },
    )

    assert response.status_code == 201
    body = response.json()
    payload = body[0]["files"][0]["payload"]
    assert body[0]["title"] == "Managed Triangle"
    assert body[0]["files"][0]["filename"] == "triangle.stl"
    assert body[0]["files"][0]["storage_status"] == "stored_compressed"
    assert payload["source_project_url"] == "https://www.printables.com/model/123-triangle"
    assert payload["source_file_url"] == "https://files.printables.com/media/prints/123/triangle.stl"
    assert payload["original_sha256"] == sha256(ASCII_STL).hexdigest()
    assert gzip_decompress(store.saved[0]["payload"].compressed_bytes) == ASCII_STL
    assert runner.download_headers == [{"Cookie": "session=abc"}]
    assert "session=abc" not in response.text


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


def test_compressed_payload_round_trips_with_hash_metadata():
    payload = compress_model_payload(ASCII_STL)

    assert payload.compression == "gzip"
    assert gzip_decompress(payload.compressed_bytes) == ASCII_STL
    assert payload.original_size_bytes == len(ASCII_STL)
    assert payload.compressed_size_bytes == len(payload.compressed_bytes)
    assert payload.original_sha256 == sha256(ASCII_STL).hexdigest()
    assert payload.compressed_sha256 == sha256(payload.compressed_bytes).hexdigest()


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
