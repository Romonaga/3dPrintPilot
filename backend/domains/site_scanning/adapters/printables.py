from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import httpx

from backend.domains.site_scanning.adapters.base import AdapterDiscoveryResult
from backend.domains.site_scanning.entities import CrawlCandidate
from backend.domains.site_scanning.runners.printables import PrintablesSourceSiteRunner
from backend.domains.site_scanning.utils import normalize_url

PRINTABLES_RUNNER_MANIFEST = PrintablesSourceSiteRunner.manifest
PRINTABLES_HOSTS = frozenset(PRINTABLES_RUNNER_MANIFEST.allowed_hosts)
MAX_CANDIDATES_PER_PAGE = 24


class PrintablesAdapter:
    site_key = PRINTABLES_RUNNER_MANIFEST.site_key
    display_name = PRINTABLES_RUNNER_MANIFEST.display_name
    allowed_hosts = PRINTABLES_HOSTS
    browser_session_hosts = frozenset(PRINTABLES_RUNNER_MANIFEST.browser_session_hosts)
    browser_session_observe_hosts = frozenset(PRINTABLES_RUNNER_MANIFEST.browser_session_observe_hosts)
    browser_session_required_cookie_names = PRINTABLES_RUNNER_MANIFEST.browser_session_required_cookie_names
    base_url = PRINTABLES_RUNNER_MANIFEST.base_url
    login_url = PRINTABLES_RUNNER_MANIFEST.login_url
    supports_downloads = PRINTABLES_RUNNER_MANIFEST.supports_downloads
    supported_auth_modes = PRINTABLES_RUNNER_MANIFEST.supported_auth_modes
    auth_storage_notes = PRINTABLES_RUNNER_MANIFEST.auth_storage_notes
    default_limits = PRINTABLES_RUNNER_MANIFEST.default_limits
    robots_terms_notes = PRINTABLES_RUNNER_MANIFEST.robots_terms_notes

    def discover(
        self,
        url: str,
        depth: int,
        parent_url: str | None,
        auth_headers: dict[str, str] | None = None,
    ) -> AdapterDiscoveryResult:
        normalized_url = normalize_url(url)
        parsed = urlparse(normalized_url)
        if parsed.netloc not in PRINTABLES_HOSTS:
            return AdapterDiscoveryResult(candidates=(), discovered_urls=())
        if parsed.path.startswith("/world/"):
            return AdapterDiscoveryResult(candidates=(), discovered_urls=())

        html_text = _fetch_public_page(normalized_url, auth_headers=auth_headers)
        candidates = _extract_print_candidates(html_text, normalized_url, depth, parent_url)
        if not candidates and _is_model_url(normalized_url):
            candidates = (_candidate_from_model_url(normalized_url, depth, parent_url),)
        discovered_urls = tuple(candidate.normalized_url for candidate in candidates)
        return AdapterDiscoveryResult(candidates=candidates, discovered_urls=discovered_urls)


def _fetch_public_page(url: str, auth_headers: dict[str, str] | None = None) -> str:
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": "3dPrintPilot/0.1 local compatibility checker",
    }
    headers.update(auth_headers or {})
    with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _extract_print_candidates(page_html: str, page_url: str, depth: int, parent_url: str | None) -> tuple[CrawlCandidate, ...]:
    by_url: dict[str, CrawlCandidate] = {}
    for raw_model in _iter_embedded_print_objects(page_html):
        model_id = str(raw_model.get("id") or "").strip()
        slug = str(raw_model.get("slug") or "").strip()
        name = str(raw_model.get("name") or "").strip()
        if not model_id or not slug or not name:
            continue
        model_url = _canonical_printables_model_url(model_id, slug)
        by_url.setdefault(
            model_url,
            _candidate(model_url, name, depth, parent_url, "embedded public model metadata", external_model_id=model_id),
        )
        if len(by_url) >= MAX_CANDIDATES_PER_PAGE:
            break

    if len(by_url) < MAX_CANDIDATES_PER_PAGE:
        for model_id, model_url, title in _iter_model_links(page_html, page_url):
            by_url.setdefault(
                model_url,
                _candidate(model_url, title, depth, parent_url, "public model link", external_model_id=model_id),
            )
            if len(by_url) >= MAX_CANDIDATES_PER_PAGE:
                break

    return tuple(by_url.values())


def _iter_embedded_print_objects(page_html: str):
    pattern = re.compile(
        r'"id":"(?P<id>\d+)","name":"(?P<name>(?:\\.|[^"\\])+)","slug":"(?P<slug>[^"]+)".{0,2500}?"__typename":"PrintType"',
        re.DOTALL,
    )
    for match in pattern.finditer(page_html):
        yield {
            "id": match.group("id"),
            "name": _decode_jsonish_string(match.group("name")),
            "slug": match.group("slug"),
        }


def _decode_jsonish_string(value: str) -> str:
    return bytes(value, "utf-8").decode("unicode_escape")


def _iter_model_links(page_html: str, page_url: str):
    pattern = re.compile(r'href="(?P<href>/model/(?P<id>\d+)-(?P<slug>[^"#?/]+)(?:/[^"#?]*)?)"')
    for match in pattern.finditer(page_html):
        model_url = _canonical_printables_model_url(match.group("id"), match.group("slug"))
        title = _title_from_slug(match.group("slug"))
        yield match.group("id"), model_url, title


def _candidate(
    model_url: str,
    title: str,
    depth: int,
    parent_url: str | None,
    reason: str,
    external_model_id: str | None = None,
) -> CrawlCandidate:
    return CrawlCandidate(
        source_url=model_url,
        title=html.unescape(title),
        depth=depth,
        parent_url=parent_url,
        normalized_url=model_url,
        inclusion_reason=reason,
        status="needs_file",
        confidence=0.58,
        evidence=(
            "Extracted from public Printables page metadata.",
            "No files were downloaded; compatibility remains metadata-only.",
        ),
        external_model_id=external_model_id,
        license="unknown",
        attribution="Printables",
        requirements={"file_format": None, "material": None},
        raw_payload={
            "external_model_id": external_model_id,
            "source": "public_printables_metadata",
            "metadata_only": True,
        },
    )


def _candidate_from_model_url(model_url: str, depth: int, parent_url: str | None) -> CrawlCandidate:
    parsed = urlparse(model_url)
    model_id, slug = _printables_model_parts(parsed.path)
    canonical_url = _canonical_printables_model_url(model_id, slug) if model_id and slug else model_url
    title_slug = slug or parsed.path.rstrip("/").split("/")[-1].split("-", 1)[-1]
    return _candidate(canonical_url, _title_from_slug(title_slug), depth, parent_url, "public model URL", model_id)


def _is_model_url(url: str) -> bool:
    return re.search(r"/model/\d+[-/]", url) is not None


def _title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip() or "Printables model"


def _canonical_printables_model_url(model_id: str, slug: str) -> str:
    return normalize_url(f"https://www.printables.com/model/{model_id}-{slug}")


def _printables_model_parts(path: str) -> tuple[str | None, str | None]:
    match = re.search(r"/model/(?P<id>\d+)-(?P<slug>[^/?#]+)", path)
    if match is None:
        return None, None
    return match.group("id"), match.group("slug")
