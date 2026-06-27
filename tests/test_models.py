from __future__ import annotations

from datetime import UTC, datetime
from gzip import decompress as gzip_decompress
from hashlib import sha256
from io import BytesIO
import json
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
        self.model_files = {}
        self.slicer_artifacts = []

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

    def get_model_file(self, model_id, file_id):
        return self.model_files.get((model_id, file_id))

    def list_slicer_artifacts(self, model_id, file_id):
        if (model_id, file_id) not in self.model_files:
            return []
        return [artifact for artifact in self.slicer_artifacts if artifact.model_file_id == file_id]

    def get_slicer_artifact(self, model_id, file_id, artifact_id):
        if (model_id, file_id) not in self.model_files:
            return None
        return next((artifact for artifact in self.slicer_artifacts if artifact.id == artifact_id and artifact.model_file_id == file_id), None)

    def save_slicer_artifact(self, **kwargs):
        if (kwargs["model_id"], kwargs["file_id"]) not in self.model_files:
            raise ValueError("Model file not found")
        payload = kwargs["payload"]
        now = datetime.now(UTC)
        artifact = SimpleNamespace(
            id=31 + len(self.slicer_artifacts),
            model_file_id=kwargs["file_id"],
            printer_id=kwargs["printer_id"],
            created_by_user_id=kwargs["created_by_user_id"],
            output_filename=kwargs["output_filename"],
            output_format=kwargs["output_format"],
            content_type=kwargs["content_type"],
            slicer_name=kwargs["slicer_name"],
            slicer_version=kwargs["slicer_version"],
            profile_name=kwargs["profile_name"],
            settings=kwargs["settings"],
            settings_hash=kwargs["settings_hash"],
            status="stored",
            compression=payload.compression,
            compressed_bytes=payload.compressed_bytes,
            original_size_bytes=payload.original_size_bytes,
            compressed_size_bytes=payload.compressed_size_bytes,
            original_sha256=payload.original_sha256,
            compressed_sha256=payload.compressed_sha256,
            created_at=now,
            updated_at=now,
        )
        self.slicer_artifacts.insert(0, artifact)
        return artifact

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
            model_id=3,
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
        model = SimpleNamespace(
            id=3,
            title=kwargs["title"],
            source_url=kwargs["source_url"],
            status="analyzed",
            created_at=now,
            updated_at=now,
            files=[model_file],
        )
        self.model_files[(model.id, model_file.id)] = model_file
        return model

    def save_downloaded_model(self, **kwargs):
        self.saved.append(kwargs)
        now = datetime.now(UTC)
        analysis = kwargs["analysis"]
        compressed_payload = kwargs["payload"]
        payload = SimpleNamespace(
            source_project_url=kwargs["source_project_url"],
            source_file_url=kwargs["source_file_url"],
            compression=compressed_payload.compression,
            compressed_bytes=compressed_payload.compressed_bytes,
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
            model_id=4,
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
        model = SimpleNamespace(
            id=4,
            title=kwargs["title"],
            source_url=kwargs["source_project_url"],
            status="analyzed",
            created_at=now,
            updated_at=now,
            files=[model_file],
        )
        self.model_files[(model.id, model_file.id)] = model_file
        return model


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
                SourceSiteFile(
                    file_id="archive-1",
                    filename="Download all files.zip",
                    file_format="zip",
                    size_bytes=512,
                    source_file_url="https://www.printables.com/model/123-triangle/files#download-pack-archive-1",
                    supported_model_file=True,
                    notes="Printables download-all archive; supported STL and 3MF files will be imported.",
                ),
            ),
        )

    def download_project_file(self, project_url, file_id, *, auth_headers=None, max_bytes):
        self.download_headers.append(auth_headers)
        assert project_url == "https://www.printables.com/model/123-triangle"
        assert max_bytes == MAX_UPLOAD_BYTES
        if file_id == "archive-1":
            return SourceSiteDownloadedFile(
                file_id=file_id,
                filename="Download all files.zip",
                content_type="application/zip",
                data=_sample_model_archive(),
                source_project_url="https://www.printables.com/model/123-triangle",
                source_file_url="https://files.printables.com/media/prints/123/all-files.zip",
            )
        assert file_id == "stl-1"
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


def test_model_file_payload_restore_downloads_original_bytes_from_db():
    store = FakeModelStore()
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: store
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    created = client.post(
        "/api/models/imports/downloaded-file",
        data={
            "title": "Downloaded Triangle",
            "source_project_url": "https://models.example/projects/triangle",
            "source_file_url": "https://cdn.models.example/files/triangle.stl",
        },
        files={"file": ("../unsafe-name.stl", ASCII_STL, "model/stl")},
    )

    assert created.status_code == 201
    restored = client.get("/api/models/4/files/8/payload")

    assert restored.status_code == 200
    assert restored.content == ASCII_STL
    assert restored.headers["content-type"].startswith("model/stl")
    assert "unsafe-name.stl" in restored.headers["content-disposition"]


def test_model_file_payload_restore_returns_404_when_payload_is_not_stored():
    store = FakeModelStore()
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: store
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    created = client.post(
        "/api/models/uploads",
        data={"title": "Uploaded Triangle"},
        files={"file": ("triangle.stl", ASCII_STL, "model/stl")},
    )

    assert created.status_code == 201
    restored = client.get("/api/models/3/files/7/payload")

    assert restored.status_code == 404
    assert restored.json()["detail"] == "Model file payload is not stored"


def test_slicer_artifacts_attach_multiple_outputs_to_model_file_and_restore_bytes():
    store = FakeModelStore()
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: store
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)
    uploaded = client.post(
        "/api/models/uploads",
        data={"title": "Uploaded Triangle"},
        files={"file": ("triangle.stl", ASCII_STL, "model/stl")},
    )
    first_gcode = b"; first profile\nG1 X1 Y1\n"
    second_gcode = b"; second profile\nG1 X2 Y2\n"

    assert uploaded.status_code == 201
    first = client.post(
        "/api/models/3/files/7/slicer-artifacts",
        data={
            "slicer_name": "PrusaSlicer",
            "slicer_version": "2.9.0",
            "printer_id": "44",
            "profile_name": "MK4S 0.4mm PLA",
            "settings_json": "{\"layer_height\":0.2,\"supports\":false}",
        },
        files={"file": ("triangle.gcode", first_gcode, "text/x.gcode")},
    )
    second = client.post(
        "/api/models/3/files/7/slicer-artifacts",
        data={
            "slicer_name": "PrusaSlicer",
            "profile_name": "MK4S 0.25mm PLA",
            "settings_json": "{\"layer_height\":0.1,\"supports\":true}",
        },
        files={"file": ("triangle-fine.bgcode", second_gcode, "application/octet-stream")},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    first_body = first.json()
    assert first_body["model_file_id"] == 7
    assert first_body["printer_id"] == 44
    assert first_body["output_filename"] == "triangle.gcode"
    assert first_body["output_format"] == "gcode"
    assert first_body["settings_hash"] == sha256(json.dumps({"layer_height": 0.2, "supports": False}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert first_body["original_sha256"] == sha256(first_gcode).hexdigest()
    assert "compressed_bytes" not in first.text
    assert gzip_decompress(store.slicer_artifacts[1].compressed_bytes) == first_gcode

    listed = client.get("/api/models/3/files/7/slicer-artifacts")
    restored = client.get("/api/models/3/files/7/slicer-artifacts/31/payload")

    assert listed.status_code == 200
    assert [artifact["output_filename"] for artifact in listed.json()] == ["triangle-fine.bgcode", "triangle.gcode"]
    assert restored.status_code == 200
    assert restored.content == first_gcode
    assert "triangle.gcode" in restored.headers["content-disposition"]


def test_slicer_artifact_create_returns_404_for_unknown_model_file():
    app = create_app()
    app.dependency_overrides[get_model_store] = lambda: FakeModelStore()
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post(
        "/api/models/404/files/7/slicer-artifacts",
        data={"slicer_name": "PrusaSlicer", "settings_json": "{}"},
        files={"file": ("triangle.gcode", b"G1 X1\n", "text/x.gcode")},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Model file not found"


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
    assert body["files"][2]["filename"] == "Download all files.zip"
    assert body["files"][2]["supported_model_file"] is True
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


def test_model_source_file_import_expands_printables_archive(monkeypatch):
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
            "file_ids": ["archive-1"],
            "title": "",
        },
    )

    assert response.status_code == 201
    body = response.json()
    payload = body[0]["files"][0]["payload"]
    assert len(body) == 1
    assert body[0]["title"] == "triangle.stl"
    assert body[0]["files"][0]["filename"] == "triangle.stl"
    assert payload["source_file_url"] == "https://files.printables.com/media/prints/123/all-files.zip#models/triangle.stl"
    assert gzip_decompress(store.saved[0]["payload"].compressed_bytes) == ASCII_STL
    assert runner.download_headers == [{"Cookie": "session=abc"}]


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


def _sample_model_archive() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("models/triangle.stl", ASCII_STL)
        archive.writestr("notes/readme.txt", b"Build notes")
    return buffer.getvalue()
