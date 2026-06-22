from __future__ import annotations

from backend.domains.site_scanning.adapters.printables import PrintablesAdapter
from backend.domains.site_scanning.entities import CrawlPolicy, ScanStopReason
from backend.domains.site_scanning.runners import SourceSiteCapability, SourceSiteSupportLevel, default_runner_registry
from backend.domains.site_scanning.runners.printables import PrintablesSourceSiteRunner
from backend.domains.site_scanning.service import SiteScanService


PRINTABLES_HTML = """
<html><body>
<script>
{"id":"229198","name":"Printables Calibration Cube","slug":"printables-calibration-cube","downloadCount":1463,"__typename":"PrintType"}
{"id":"62800","name":"XYZ - 20mm Calibration Cube","slug":"xyz-20mm-calibration-cube-with-mini-tests","downloadCount":1210,"__typename":"PrintType"}
</script>
</body></html>
"""

PRINTABLES_DUPLICATE_LINK_HTML = """
<html><body>
<a href="/model/229198-printables-calibration-cube">Model</a>
<a href="/model/229198-printables-calibration-cube/files">Files</a>
<a href="/model/229198-printables-calibration-cube/comments">Comments</a>
</body></html>
"""


class FakePrintablesAdapter(PrintablesAdapter):
    def discover(self, url: str, depth: int, parent_url: str | None, auth_headers=None):
        from backend.domains.site_scanning.adapters.printables import _extract_print_candidates
        from backend.domains.site_scanning.adapters.base import AdapterDiscoveryResult

        candidates = _extract_print_candidates(PRINTABLES_HTML, url, depth, parent_url)
        discovered_urls = tuple(candidate.normalized_url for candidate in candidates)
        return AdapterDiscoveryResult(candidates=candidates, discovered_urls=discovered_urls)


def test_auto_selects_printables_adapter_and_extracts_model_candidates():
    service = SiteScanService(adapters={"printables": FakePrintablesAdapter()})

    result = service.scan("https://www.printables.com/", policy=CrawlPolicy(max_depth=0, max_pages=10), site_key="auto")

    assert result.summary.site_key == "printables"
    assert result.summary.accepted_result_count == 2
    assert result.candidates[0].source_url.startswith("https://www.printables.com/model/")
    assert result.candidates[0].status == "needs_file"


def test_printables_runner_self_registers_supported_capabilities():
    registry = default_runner_registry()
    manifest = registry.manifest_for("printables")

    assert manifest is not None
    assert manifest.site_key == "printables"
    assert manifest.support_level == SourceSiteSupportLevel.PARTIAL
    assert SourceSiteCapability.PUBLIC_SCAN in manifest.capabilities
    assert SourceSiteCapability.ACCOUNT_SETUP in manifest.capabilities
    assert SourceSiteCapability.PROJECT_LOOKUP in manifest.capabilities
    assert SourceSiteCapability.FILE_DOWNLOAD not in manifest.capabilities


def test_printables_runner_identifies_project_urls_without_guessing_other_hosts():
    runner = PrintablesSourceSiteRunner()

    project = runner.identify_project("https://www.printables.com/model/229198-printables-calibration-cube/files")

    assert project is not None
    assert project.external_project_id == "229198"
    assert project.slug == "printables-calibration-cube"
    assert project.source_url == "https://www.printables.com/model/229198-printables-calibration-cube"
    assert runner.identify_project("https://example.com/model/229198-printables-calibration-cube") is None
    assert runner.identify_project("not-a-url") is None


def test_printables_child_urls_are_limited_by_shared_depth_guard():
    service = SiteScanService(adapters={"printables": FakePrintablesAdapter()})

    result = service.scan("https://www.printables.com/", policy=CrawlPolicy(max_depth=0, max_pages=10), site_key="auto")

    assert result.summary.stop_reason == ScanStopReason.DEPTH_LIMIT
    assert result.summary.rejected_url_count == 2
    assert all("exceeds limit" in rejection.reason for rejection in result.rejections)


def test_scan_passes_site_auth_headers_to_printables_adapter():
    class AuthAwarePrintablesAdapter(PrintablesAdapter):
        observed_headers = None

        def discover(self, url: str, depth: int, parent_url: str | None, auth_headers=None):
            from backend.domains.site_scanning.adapters.base import AdapterDiscoveryResult

            self.observed_headers = auth_headers
            return AdapterDiscoveryResult(candidates=(), discovered_urls=())

    adapter = AuthAwarePrintablesAdapter()
    service = SiteScanService(adapters={"printables": adapter})

    service.scan(
        "https://www.printables.com/model/1-test",
        policy=CrawlPolicy(max_depth=0, max_pages=1),
        auth_headers_by_site={"printables": {"Cookie": "session=abc"}},
    )

    assert adapter.observed_headers == {"Cookie": "session=abc"}


def test_printables_model_links_are_canonicalized_by_model_id():
    from backend.domains.site_scanning.adapters.printables import _extract_print_candidates

    candidates = _extract_print_candidates(
        PRINTABLES_DUPLICATE_LINK_HTML,
        "https://www.printables.com/",
        depth=0,
        parent_url=None,
    )

    assert len(candidates) == 1
    assert candidates[0].external_model_id == "229198"
    assert candidates[0].normalized_url == "https://www.printables.com/model/229198-printables-calibration-cube"


def test_scan_deduplicates_candidates_by_external_model_id():
    class DuplicateModelAdapter(PrintablesAdapter):
        def discover(self, url: str, depth: int, parent_url: str | None, auth_headers=None):
            from backend.domains.site_scanning.adapters.printables import _extract_print_candidates
            from backend.domains.site_scanning.adapters.base import AdapterDiscoveryResult

            candidates = _extract_print_candidates(PRINTABLES_DUPLICATE_LINK_HTML, url, depth, parent_url)
            return AdapterDiscoveryResult(candidates=candidates, discovered_urls=tuple(candidate.normalized_url for candidate in candidates))

    service = SiteScanService(adapters={"printables": DuplicateModelAdapter()})

    result = service.scan("https://www.printables.com/", policy=CrawlPolicy(max_depth=2, max_pages=10), site_key="auto")

    assert result.summary.accepted_result_count == 1
    assert len(result.candidates) == 1
