from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.domains.compatibility.routes import get_compatibility_store
from backend.domains.site_scanning.routes import get_site_scan_store


class FakeSiteScanRun:
    id = 123


class FakeSiteScanStore:
    def save_scan_result(self, result, requested_by_user_id=None):
        return FakeSiteScanRun()


class EmptyCompatibilityStore:
    def list_candidate_results(self, scan_run_id, max_candidates):
        return []

    def list_printers(self, printer_ids=None):
        return []


def test_health_endpoint_returns_app_status():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ai_accounting_status_advertises_estimated_and_final_costs():
    client = TestClient(create_app())

    response = client.get("/api/ai/accounting/status")

    assert response.status_code == 200
    assert response.json()["estimated_cost_supported"] is True
    assert response.json()["final_cost_supported"] is True
    assert response.json()["reconciliation_required"] is True


def test_site_scanning_api_returns_metrics_for_metadata_only_scan():
    app = create_app()
    app.dependency_overrides[get_site_scan_store] = lambda: FakeSiteScanStore()
    client = TestClient(app)

    response = client.post(
        "/api/site-scanning/scans",
        json={"url": "https://example.com/models/calibration-cube", "max_depth": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["status"] == "completed"
    assert body["summary"]["scan_run_id"] == 123
    assert body["summary"]["scanned_url_count"] == 1
    assert body["summary"]["accepted_result_count"] == 1
    assert body["summary"]["duration_ms"] >= 0
    assert body["candidates"][0]["status"] == "needs_file"


def test_compatibility_api_requires_scan_candidates():
    app = create_app()
    app.dependency_overrides[get_compatibility_store] = lambda: EmptyCompatibilityStore()
    client = TestClient(app)

    response = client.post("/api/compatibility/checks", json={"scan_run_id": 999, "max_candidates": 5})

    assert response.status_code == 404
    assert response.json()["detail"] == "No model candidates found for scan run"
