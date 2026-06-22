from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.domains.compatibility.routes import get_compatibility_store
from backend.domains.site_scanning.browser_link import BrowserLinkStart, BrowserLinkStatus
from backend.domains.site_scanning.routes import (
    get_site_auth_browser_link_service,
    get_site_auth_profile_store,
    get_site_scan_store,
)
from backend.domains.site_scanning.store import SiteAuthReadiness
from tests.helpers import allow_anonymous_until_bootstrap


class FakeSiteScanRun:
    id = 123


class FakeSiteScanStore:
    def enabled_site_keys(self, declarations):
        return frozenset(declaration.site_key for declaration in declarations)

    def list_adapter_records(self, declarations):
        return [
            type(
                "FakeAdapterRecord",
                (),
                {
                    "site_key": declaration.site_key,
                    "display_name": declaration.display_name,
                    "base_url": declaration.base_url,
                    "login_url": declaration.login_url,
                    "enabled": declaration.enabled,
                    "supports_downloads": declaration.supports_downloads,
                    "auth_capabilities": {
                        "supported_auth_modes": list(declaration.supported_auth_modes),
                        "auth_storage_notes": declaration.auth_storage_notes,
                    },
                    "allowed_hosts": {"hosts": list(declaration.allowed_hosts)},
                    "default_limits": declaration.default_limits,
                    "robots_terms_notes": declaration.robots_terms_notes,
                },
            )()
            for declaration in declarations
        ]

    def save_scan_result(self, result, requested_by_user_id=None):
        return FakeSiteScanRun()


class FakeSiteAuthProfile:
    def __init__(self):
        self.site_key = "printables"
        self.auth_mode = "bearer_token"
        self.label = "Personal account"
        self.account_identifier = "maker@example.test"
        self.header_name = None
        self.encrypted_value = "encrypted-secret"
        self.last_four = "1234"
        self.enabled = True
        self.updated_at = None


class FakeSiteAuthProfileStore:
    def __init__(self):
        self.profile = FakeSiteAuthProfile()
        self.deleted = False
        self.saved_secret_values = []

    def list_profile_statuses(self, declarations):
        return [(declaration, self.profile if declaration.site_key == "printables" and not self.deleted else None) for declaration in declarations]

    def upsert_profile(self, declarations, **kwargs):
        secret_value = kwargs["secret_value"]
        if kwargs["auth_mode"] == "bearer_token":
            assert secret_value == "do-not-return-this-token-1234"
            self.profile.last_four = "1234"
            self.profile.encrypted_value = "encrypted-secret"
        elif kwargs["auth_mode"] == "browser_session":
            assert kwargs["account_identifier"] == "maker@example.test"
            self.profile.last_four = secret_value[-4:] if secret_value else None
            self.profile.encrypted_value = "encrypted-browser-session" if secret_value else None
        else:
            raise AssertionError(f"Unexpected auth mode {kwargs['auth_mode']}")
        self.saved_secret_values.append(secret_value)
        self.profile.auth_mode = kwargs["auth_mode"]
        self.profile.label = kwargs.get("label")
        self.profile.account_identifier = kwargs.get("account_identifier")
        self.profile.enabled = kwargs.get("enabled", True)
        return self.profile

    def delete_profile(self, site_key):
        self.deleted = site_key == "printables"
        return self.deleted

    def get_profile(self, site_key):
        return self.profile if site_key == "printables" and not self.deleted else None

    def readiness_for_site(self, declarations, site_key):
        return SiteAuthReadiness(
            site_key="printables",
            auth_mode=self.profile.auth_mode,
            auth_ready=self.profile.encrypted_value is not None,
            link_status="linked" if self.profile.encrypted_value is not None else "needs_relink",
            message="Stored account link is available for unattended authenticated requests."
            if self.profile.encrypted_value is not None
            else "Browser session is not stored yet. Complete browser login and save a Printables session value.",
            configured=self.profile.encrypted_value is not None,
            enabled=True,
        )


class FakeBrowserLinkService:
    def start(self, *, site_key, login_url, allowed_hosts):
        assert site_key == "printables"
        assert "printables.com" in allowed_hosts
        return BrowserLinkStart(
            session_id="session-1",
            status="running",
            message="Login browser launched.",
            login_url=login_url,
            expires_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )

    def request_capture(self, session_id):
        assert session_id == "session-1"
        return BrowserLinkStatus(
            session_id=session_id,
            status="linked",
            message="Signed-in site session captured.",
            login_url="https://www.printables.com/login",
            expires_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            cookie_header="printables_session=do-not-return-this-cookie",
            cookie_count=1,
        )

    def status(self, session_id):
        return self.request_capture(session_id)


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
    assert "account_identifier" not in str(body["tables"]["site_auth_profiles"])
    assert "model_file_payloads" in body["tables"]
    assert "compressed_bytes" not in str(body["tables"]["model_file_payloads"])


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
    assert printables_profile["masked_account_identifier"] == "m***@example.test"
    assert printables_profile["auth_ready"] is True
    assert printables_profile["link_status"] == "linked"

    save_response = client.put(
        "/api/site-scanning/auth-profiles/printables",
        json={
            "auth_mode": "bearer_token",
            "secret_value": "do-not-return-this-token-1234",
            "label": "Personal account",
            "account_identifier": "maker@example.test",
        },
    )
    assert save_response.status_code == 200
    assert save_response.json()["configured"] is True
    assert "do-not-return-this-token" not in save_response.text

    delete_response = client.delete("/api/site-scanning/auth-profiles/printables")
    assert delete_response.status_code == 204


def test_site_auth_profile_browser_link_api_never_requests_google_passwords():
    app = create_app()
    app.dependency_overrides[get_site_auth_profile_store] = lambda: FakeSiteAuthProfileStore()
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    link_response = client.get("/api/site-scanning/auth-profiles/printables/link")
    assert link_response.status_code == 200
    link_body = link_response.json()
    assert link_body["auth_mode"] == "browser_session"
    assert link_body["login_url"] == "https://www.printables.com/login"
    assert "secret_value" not in link_body
    assert "oauth_token" not in link_body
    assert "Printables session value" in link_body["storage_notes"]

    test_response = client.post("/api/site-scanning/auth-profiles/printables/test")
    assert test_response.status_code == 200
    test_body = test_response.json()
    assert test_body["auth_ready"] is True
    assert test_body["link_status"] == "linked"
    assert "encrypted-secret" not in test_response.text


def test_site_auth_browser_link_capture_stores_cookie_without_returning_it():
    app = create_app()
    fake_store = FakeSiteAuthProfileStore()
    app.dependency_overrides[get_site_auth_profile_store] = lambda: fake_store
    app.dependency_overrides[get_site_auth_browser_link_service] = lambda: FakeBrowserLinkService()
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    start_response = client.post(
        "/api/site-scanning/auth-profiles/printables/browser-link",
        json={"label": "Google account", "account_identifier": "maker@example.test"},
    )
    assert start_response.status_code == 200
    start_body = start_response.json()
    assert start_body["session_id"] == "session-1"
    assert start_body["status"] == "running"
    assert start_body["auth_profile"]["link_status"] == "needs_relink"
    assert "do-not-return-this-cookie" not in start_response.text

    capture_response = client.post("/api/site-scanning/auth-profiles/printables/browser-link/session-1/capture")
    assert capture_response.status_code == 200
    capture_body = capture_response.json()
    assert capture_body["status"] == "linked"
    assert capture_body["cookie_count"] == 1
    assert capture_body["auth_profile"]["auth_ready"] is True
    assert fake_store.saved_secret_values[-1] == "printables_session=do-not-return-this-cookie"
    assert "do-not-return-this-cookie" not in capture_response.text


def test_site_scanning_adapter_api_exposes_printables_auth_capabilities():
    app = create_app()
    app.dependency_overrides[get_site_scan_store] = lambda: FakeSiteScanStore()
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.get("/api/site-scanning/adapters")

    assert response.status_code == 200
    printables = next(adapter for adapter in response.json() if adapter["site_key"] == "printables")
    assert printables["base_url"] == "https://www.printables.com/"
    assert printables["login_url"] == "https://www.printables.com/login"
    assert "username_password" in printables["supported_auth_modes"]
    assert "browser_session" in printables["supported_auth_modes"]


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
