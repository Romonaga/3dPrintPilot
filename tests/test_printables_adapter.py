from __future__ import annotations

import backend.domains.site_scanning.runners.printables as printables_runner_module
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
    assert SourceSiteCapability.FILE_LISTING in manifest.capabilities
    assert SourceSiteCapability.FILE_DOWNLOAD in manifest.capabilities


def test_printables_runner_identifies_project_urls_without_guessing_other_hosts():
    runner = PrintablesSourceSiteRunner()

    project = runner.identify_project("https://www.printables.com/model/229198-printables-calibration-cube/files")

    assert project is not None
    assert project.external_project_id == "229198"
    assert project.slug == "printables-calibration-cube"
    assert project.source_url == "https://www.printables.com/model/229198-printables-calibration-cube"
    assert runner.identify_project("https://example.com/model/229198-printables-calibration-cube") is None
    assert runner.identify_project("not-a-url") is None


def test_printables_runner_lists_project_files_and_marks_unsupported_extensions(monkeypatch):
    def fake_post_graphql(query, variables, *, auth_headers=None):
        assert variables == {"id": "229198"}
        assert auth_headers == {"Cookie": "session=abc"}
        return {
            "data": {
                "model": {
                    "id": "229198",
                    "name": "Calibration Cube",
                    "stls": [
                        {"id": "file-2", "name": "helper.scad", "fileSize": 100, "order": 2},
                        {"id": "file-1", "name": "cube.stl", "fileSize": 2048, "order": 1},
                    ],
                }
            }
        }

    monkeypatch.setattr(printables_runner_module, "_post_graphql", fake_post_graphql)
    runner = PrintablesSourceSiteRunner()

    project_files = runner.list_project_files(
        "https://www.printables.com/model/229198-printables-calibration-cube/files",
        auth_headers={"Cookie": "session=abc"},
    )

    assert project_files.project_title == "Calibration Cube"
    assert [item.filename for item in project_files.files] == ["cube.stl", "helper.scad"]
    assert project_files.files[0].supported_model_file is True
    assert project_files.files[0].source_file_url.endswith("/files#file-file-1")
    assert project_files.files[1].file_format == "scad"
    assert project_files.files[1].supported_model_file is False


def test_printables_runner_downloads_selected_model_file_with_site_download_link(monkeypatch):
    observed_mutation_variables = None

    def fake_post_graphql(query, variables, *, auth_headers=None):
        nonlocal observed_mutation_variables
        assert auth_headers == {"Cookie": "session=abc"}
        if "query ModelFiles" in query:
            return {
                "data": {
                    "model": {
                        "id": "229198",
                        "name": "Calibration Cube",
                        "stls": [{"id": "file-1", "name": "cube.3mf", "fileSize": 2048, "order": 1}],
                    }
                }
            }
        observed_mutation_variables = variables
        return {
            "data": {
                "getDownloadLink": {
                    "ok": True,
                    "errors": [],
                    "output": {"link": "https://files.printables.com/media/prints/229198/cube.3mf"},
                }
            }
        }

    def fake_download_bytes(url, *, auth_headers=None, max_bytes):
        assert url == "https://files.printables.com/media/prints/229198/cube.3mf"
        assert auth_headers == {"Cookie": "session=abc"}
        assert max_bytes == 1024
        return b"3mf-data", "model/3mf"

    monkeypatch.setattr(printables_runner_module, "_post_graphql", fake_post_graphql)
    monkeypatch.setattr(printables_runner_module, "_download_bytes", fake_download_bytes)
    runner = PrintablesSourceSiteRunner()

    downloaded = runner.download_project_file(
        "https://www.printables.com/model/229198-printables-calibration-cube",
        "file-1",
        auth_headers={"Cookie": "session=abc"},
        max_bytes=1024,
    )

    assert observed_mutation_variables == {
        "id": "file-1",
        "modelId": "229198",
        "fileType": "stl",
        "source": "model_detail",
    }
    assert downloaded.filename == "cube.3mf"
    assert downloaded.content_type == "model/3mf"
    assert downloaded.data == b"3mf-data"
    assert downloaded.source_file_url == "https://files.printables.com/media/prints/229198/cube.3mf"


def test_printables_graphql_requests_are_throttled(monkeypatch):
    throttle_calls = []

    class FakeGraphqlResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"ok": True}}

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def post(self, url, json):
            assert url == printables_runner_module.PRINTABLES_GRAPHQL_URL
            return FakeGraphqlResponse()

    def fake_wait(url, *, min_interval_seconds=None):
        throttle_calls.append((url, min_interval_seconds))

    monkeypatch.setattr(printables_runner_module.httpx, "Client", FakeClient)
    monkeypatch.setattr(printables_runner_module.source_site_request_throttler, "wait", fake_wait)

    payload = printables_runner_module._post_graphql("query Test { ok }", {})

    assert payload == {"data": {"ok": True}}
    assert throttle_calls == [
        (
            printables_runner_module.PRINTABLES_GRAPHQL_URL,
            printables_runner_module.PRINTABLES_REQUEST_MIN_INTERVAL_SECONDS,
        )
    ]


def test_printables_file_download_requests_are_throttled(monkeypatch):
    throttle_calls = []

    class FakeUrl:
        scheme = "https"
        host = printables_runner_module.PRINTABLES_FILES_HOST

    class FakeDownloadResponse:
        url = FakeUrl()
        headers = {"content-type": "model/stl"}

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"solid sample"

    class FakeStream:
        def __enter__(self):
            return FakeDownloadResponse()

        def __exit__(self, exc_type, exc, traceback):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def stream(self, method, url):
            assert method == "GET"
            assert url == "https://files.printables.com/media/prints/229198/cube.stl"
            return FakeStream()

    def fake_wait(url, *, min_interval_seconds=None):
        throttle_calls.append((url, min_interval_seconds))

    monkeypatch.setattr(printables_runner_module.httpx, "Client", FakeClient)
    monkeypatch.setattr(printables_runner_module.source_site_request_throttler, "wait", fake_wait)

    data, content_type = printables_runner_module._download_bytes(
        "https://files.printables.com/media/prints/229198/cube.stl",
        max_bytes=1024,
    )

    assert data == b"solid sample"
    assert content_type == "model/stl"
    assert throttle_calls == [
        (
            "https://files.printables.com/media/prints/229198/cube.stl",
            printables_runner_module.PRINTABLES_REQUEST_MIN_INTERVAL_SECONDS,
        )
    ]


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
