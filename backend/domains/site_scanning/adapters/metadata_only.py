from __future__ import annotations

from urllib.parse import urlparse

from backend.domains.site_scanning.adapters.base import AdapterDiscoveryResult
from backend.domains.site_scanning.entities import CrawlCandidate
from backend.domains.site_scanning.utils import normalize_url


class MetadataOnlyAdapter:
    site_key = "metadata_only"
    display_name = "Metadata-only URL capture"
    allowed_hosts = frozenset[str]()
    supports_downloads = False

    def discover(self, url: str, depth: int, parent_url: str | None) -> AdapterDiscoveryResult:
        normalized_url = normalize_url(url)
        parsed = urlparse(normalized_url)
        path_name = parsed.path.rstrip("/").split("/")[-1] or parsed.netloc
        readable_name = path_name.replace("-", " ").replace("_", " ").strip() or normalized_url
        candidate = CrawlCandidate(
            source_url=url,
            title=readable_name,
            depth=depth,
            parent_url=parent_url,
            normalized_url=normalized_url,
            inclusion_reason="user supplied URL captured as metadata-only candidate",
            status="needs_file",
            confidence=0.35,
            evidence=("No file geometry has been analyzed yet.", "Compatibility will be metadata-only until upload."),
        )
        return AdapterDiscoveryResult(candidates=(candidate,), discovered_urls=())
