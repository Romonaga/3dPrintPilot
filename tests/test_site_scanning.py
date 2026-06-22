from __future__ import annotations

from backend.domains.site_scanning.adapters.base import AdapterDiscoveryResult
from backend.domains.site_scanning.entities import CrawlCandidate, CrawlPolicy, ScanStopReason
from backend.domains.site_scanning.models import ModelSiteScanResult, ModelSiteScanRun
from backend.domains.site_scanning.service import SiteScanService
from backend.domains.site_scanning.store import SiteScanStore
from backend.domains.site_scanning.utils import normalize_url


class BranchingAdapter:
    site_key = "branching"
    display_name = "Branching test adapter"
    allowed_hosts = frozenset[str]()
    supports_downloads = False

    def discover(
        self,
        url: str,
        depth: int,
        parent_url: str | None,
        auth_headers: dict[str, str] | None = None,
    ) -> AdapterDiscoveryResult:
        normalized_url = normalize_url(url)
        candidate = CrawlCandidate(
            source_url=url,
            title=f"candidate-depth-{depth}",
            depth=depth,
            parent_url=parent_url,
            normalized_url=normalized_url,
            inclusion_reason="test adapter candidate",
            status="needs_file",
            confidence=0.5,
        )
        children = (
            "https://models.example/child-a",
            "https://models.example/child-b",
            "https://outside.example/model",
        )
        return AdapterDiscoveryResult(candidates=(candidate,), discovered_urls=children if depth == 0 else ())


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, item):
        self.added.append(item)

    def flush(self):
        for item in self.added:
            if isinstance(item, ModelSiteScanRun):
                item.id = 42

    def commit(self):
        self.committed = True

    def refresh(self, item):
        return None


def test_metadata_only_scan_records_status_timing_and_counts():
    service = SiteScanService()

    result = service.scan("https://example.com/models/calibration-cube", policy=CrawlPolicy(max_depth=1))

    assert result.summary.status == "completed"
    assert result.summary.stop_reason == ScanStopReason.COMPLETED
    assert result.summary.scanned_url_count == 1
    assert result.summary.accepted_result_count == 1
    assert result.summary.rejected_url_count == 0
    assert result.summary.duration_ms >= 0
    assert result.candidates[0].status == "needs_file"
    assert result.candidates[0].depth == 0
    assert result.candidates[0].license == "unknown"
    assert result.candidates[0].attribution == "example.com"


def test_metadata_only_adapter_remains_generic_without_runner_support():
    service = SiteScanService()
    declaration = next(declaration for declaration in service.adapter_declarations() if declaration.site_key == "metadata_only")

    assert declaration.supported_auth_modes == ("none",)
    assert declaration.supports_downloads is False
    assert declaration.login_url is None
    assert declaration.allowed_hosts == ()


def test_scan_rejects_invalid_urls_with_chartable_summary():
    service = SiteScanService()

    result = service.scan("not-a-url")

    assert result.summary.status == "rejected"
    assert result.summary.stop_reason == ScanStopReason.INVALID_URL
    assert result.summary.accepted_result_count == 0
    assert result.summary.rejected_url_count == 1
    assert result.rejections[0].reason == "invalid url"


def test_scan_enforces_depth_and_domain_limits():
    service = SiteScanService(adapters={BranchingAdapter.site_key: BranchingAdapter()})

    result = service.scan(
        "https://models.example/root",
        site_key="branching",
        policy=CrawlPolicy(max_depth=0, max_pages=10, same_domain_only=True),
    )

    assert result.summary.scanned_url_count == 1
    assert result.summary.accepted_result_count == 1
    assert result.summary.rejected_url_count == 3
    assert result.summary.stop_reason in {ScanStopReason.DEPTH_LIMIT, ScanStopReason.DOMAIN_LIMIT}
    assert any(rejection.reason == "host is outside allowed domains" for rejection in result.rejections)
    assert any("exceeds limit" in rejection.reason for rejection in result.rejections)


def test_scan_enforces_page_limit_before_draining_queue():
    service = SiteScanService(adapters={BranchingAdapter.site_key: BranchingAdapter()})

    result = service.scan(
        "https://models.example/root",
        site_key="branching",
        policy=CrawlPolicy(max_depth=2, max_pages=1, same_domain_only=True),
    )

    assert result.summary.stop_reason == ScanStopReason.PAGE_LIMIT
    assert result.summary.queued_url_count == 4
    assert result.summary.scanned_url_count == 1
    assert result.summary.accepted_result_count == 1


def test_scan_rejects_disabled_adapters():
    service = SiteScanService()

    try:
        service.scan("https://example.com/models/calibration-cube", enabled_site_keys=frozenset({"printables"}))
    except ValueError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("Expected disabled adapter error")


def test_store_maps_scan_result_to_run_and_result_rows():
    service = SiteScanService()
    result = service.scan("https://example.com/models/calibration-cube")
    session = FakeSession()

    run = SiteScanStore(session).save_scan_result(result)

    assert run.id == 42
    assert run.status == "completed"
    assert run.stop_reason == "completed"
    assert run.scanned_url_count == 1
    assert run.accepted_result_count == 1
    assert run.duration_ms >= 0
    assert session.committed is True
    result_rows = [item for item in session.added if isinstance(item, ModelSiteScanResult)]
    assert len(result_rows) == 1
    assert result_rows[0].result_type == "candidate"
    assert result_rows[0].status == "needs_file"
    assert result_rows[0].evidence["license"] == "unknown"
    assert result_rows[0].evidence["attribution"] == "example.com"
    assert result_rows[0].raw_payload["metadata_only"] is True
