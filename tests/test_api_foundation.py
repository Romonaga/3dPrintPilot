from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.domains.compatibility.routes import get_compatibility_store
from backend.domains.site_scanning.routes import get_site_auth_profile_store, get_site_scan_store
from tests.helpers import allow_anonymous_until_bootstrap


class FakeSiteScanRun:
    id = 123


class FakeSiteScanStore:
    def enabled_site_keys(self, declarations):
        return frozenset(declaration.site_key for declaration in declarations)

    def save_scan_result(self, result, requested_by_user_id=None):
        return FakeSiteScanRun()


class FakeSiteAuthProfile:
    site_key = "printables"
    auth_mode = "bearer_token"
    label = "Personal account"
    header_name = None
    encrypted_value = "encrypted-secret"
    last_four = "1234"
    enabled = True
    updated_at = None


class FakeSiteAuthProfileStore:
    def __init__(self):
        self.profile = FakeSiteAuthProfile()
        self.deleted = False

    def list_profile_statuses(self, declarations):
        return [(declaration, self.profile if declaration.site_key == "printables" and not self.deleted else None) for declaration in declarations]

    def upsert_profile(self, declarations, **kwargs):
        assert kwargs["secret_value"] == "do-not-return-this-token-1234"
        assert kwargs["auth_mode"] == "bearer_token"
        return self.profile

    def delete_profile(self, site_key):
        self.deleted = site_key == "printables"
        return self.deleted


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
    client = TestClient(allow_anonymous_until_bootstrap(create_app()))

    response = client.get("/api/ai/accounting/status")

    assert response.status_code == 200
    assert response.json()["estimated_cost_supported"] is True
    assert response.json()["final_cost_supported"] is True
    assert response.json()["reconciliation_required"] is True


def test_operations_backup_export_redacts_provider_secret_payloads():
    client = TestClient(allow_anonymous_until_bootstrap(create_app()))

    response = client.get("/api/operations/backup.json")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "3dprintpilot.operations.backup"
    assert "provider_secrets" in body["tables"]
    assert "encrypted_value" not in str(body["tables"]["provider_secrets"])
    assert "secret_fingerprint" not in str(body["tables"]["provider_secrets"])
    assert "site_auth_profiles" in body["tables"]
    assert "encrypted_value" not in str(body["tables"]["site_auth_profiles"])
    assert "secret_fingerprint" not in str(body["tables"]["site_auth_profiles"])


def test_site_auth_profile_api_masks_secret_values():
    app = create_app()
    fake_store = FakeSiteAuthProfileStore()
    app.dependency_overrides[get_site_auth_profile_store] = lambda: fake_store
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    list_response = client.get("/api/site-scanning/auth-profiles")
    assert list_response.status_code == 200
    assert "do-not-return-this-token" not in list_response.text
    printables_profile = next(item for item in list_response.json() if item["site_key"] == "printables")
    assert printables_profile["masked_value"] == "****1234"

    save_response = client.put(
        "/api/site-scanning/auth-profiles/printables",
        json={"auth_mode": "bearer_token", "secret_value": "do-not-return-this-token-1234", "label": "Personal account"},
    )
    assert save_response.status_code == 200
    assert save_response.json()["configured"] is True
    assert "do-not-return-this-token" not in save_response.text

    delete_response = client.delete("/api/site-scanning/auth-profiles/printables")
    assert delete_response.status_code == 204


def test_site_scanning_api_returns_metrics_for_metadata_only_scan():
    app = create_app()
    app.dependency_overrides[get_site_scan_store] = lambda: FakeSiteScanStore()
    allow_anonymous_until_bootstrap(app)
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
    assert body["candidates"][0]["license"] == "unknown"
    assert body["candidates"][0]["attribution"] == "example.com"


def test_compatibility_api_requires_scan_candidates():
    app = create_app()
    app.dependency_overrides[get_compatibility_store] = lambda: EmptyCompatibilityStore()
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post("/api/compatibility/checks", json={"scan_run_id": 999, "max_candidates": 5})

    assert response.status_code == 404
    assert response.json()["detail"] == "No model candidates found for scan run"
