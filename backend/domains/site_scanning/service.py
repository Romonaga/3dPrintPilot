from __future__ import annotations

from collections import deque
from time import monotonic
from urllib.parse import urlparse

from backend.domains.site_scanning.adapters.base import SiteAdapterDeclaration, SiteScanAdapter
from backend.domains.site_scanning.adapters.metadata_only import MetadataOnlyAdapter
from backend.domains.site_scanning.adapters.printables import PRINTABLES_HOSTS, PrintablesAdapter
from backend.domains.site_scanning.entities import (
    CrawlPolicy,
    CrawlRejection,
    ScanResult,
    ScanStatus,
    ScanStopReason,
    ScanSummary,
)
from backend.domains.site_scanning.utils import try_normalize_url


class SiteScanService:
    def __init__(self, adapters: dict[str, SiteScanAdapter] | None = None) -> None:
        self._adapters = adapters or {
            MetadataOnlyAdapter.site_key: MetadataOnlyAdapter(),
            PrintablesAdapter.site_key: PrintablesAdapter(),
        }

    def list_adapters(self) -> list[SiteScanAdapter]:
        return list(self._adapters.values())

    def adapter_declarations(self) -> list[SiteAdapterDeclaration]:
        declarations = []
        for adapter in self.list_adapters():
            declarations.append(
                SiteAdapterDeclaration(
                    site_key=adapter.site_key,
                    display_name=adapter.display_name,
                    allowed_hosts=tuple(sorted(adapter.allowed_hosts)),
                    supports_downloads=adapter.supports_downloads,
                    default_limits=getattr(adapter, "default_limits", {}),
                    robots_terms_notes=getattr(adapter, "robots_terms_notes", None),
                )
            )
        return declarations

    def scan(
        self,
        start_url: str,
        policy: CrawlPolicy | None = None,
        site_key: str = "auto",
        enabled_site_keys: frozenset[str] | None = None,
    ) -> ScanResult:
        started = monotonic()
        active_policy = (policy or CrawlPolicy()).normalized()
        normalized_start_url = try_normalize_url(start_url)
        selected_site_key = self._select_site_key(site_key, normalized_start_url)
        adapter = self._adapters.get(selected_site_key)
        if adapter is None:
            raise ValueError(f"Unknown site scanning adapter: {selected_site_key}")
        if enabled_site_keys is not None and selected_site_key not in enabled_site_keys:
            raise ValueError(f"Site scanning adapter is disabled: {selected_site_key}")

        if normalized_start_url is None:
            return self._rejected_result(
                start_url=start_url,
                site_key=selected_site_key,
                policy=active_policy,
                stop_reason=ScanStopReason.INVALID_URL,
                duration_ms=_duration_ms(started),
            )

        start_host = urlparse(normalized_start_url).netloc.lower()
        allowed_hosts = _allowed_hosts(active_policy, adapter, start_host)
        if not _host_allowed(start_host, allowed_hosts):
            return self._rejected_result(
                start_url=start_url,
                site_key=selected_site_key,
                policy=active_policy,
                stop_reason=ScanStopReason.DOMAIN_LIMIT,
                duration_ms=_duration_ms(started),
                normalized_start_url=normalized_start_url,
                rejections=(CrawlRejection(source_url=start_url, reason="host is outside allowed domains", depth=0),),
            )

        queue: deque[tuple[str, int, str | None]] = deque([(normalized_start_url, 0, None)])
        seen = {normalized_start_url}
        candidates_by_key = {}
        rejections: list[CrawlRejection] = []
        scanned_url_count = 0
        stop_reason = ScanStopReason.COMPLETED

        while queue:
            if scanned_url_count >= active_policy.max_pages:
                stop_reason = ScanStopReason.PAGE_LIMIT
                break
            if monotonic() - started > active_policy.max_runtime_seconds:
                stop_reason = ScanStopReason.RUNTIME_LIMIT
                break

            current_url, depth, parent_url = queue.popleft()
            current_host = urlparse(current_url).netloc.lower()
            if active_policy.same_domain_only and not _host_allowed(current_host, allowed_hosts):
                rejections.append(
                    CrawlRejection(
                        source_url=current_url,
                        reason="host is outside allowed domains",
                        depth=depth,
                        parent_url=parent_url,
                    )
                )
                stop_reason = ScanStopReason.DOMAIN_LIMIT
                continue

            if depth > active_policy.max_depth:
                rejections.append(
                    CrawlRejection(
                        source_url=current_url,
                        reason=f"depth {depth} exceeds limit {active_policy.max_depth}",
                        depth=depth,
                        parent_url=parent_url,
                    )
                )
                stop_reason = ScanStopReason.DEPTH_LIMIT
                continue

            scanned_url_count += 1
            discovery = adapter.discover(current_url, depth=depth, parent_url=parent_url)
            for candidate in discovery.candidates:
                candidate_key = _candidate_dedupe_key(selected_site_key, candidate)
                current_candidate = candidates_by_key.get(candidate_key)
                if current_candidate is None or _candidate_rank(candidate) < _candidate_rank(current_candidate):
                    candidates_by_key[candidate_key] = candidate

            for discovered_url in discovery.discovered_urls:
                normalized_url = try_normalize_url(discovered_url)
                if normalized_url is None:
                    rejections.append(
                        CrawlRejection(
                            source_url=discovered_url,
                            reason="invalid discovered URL",
                            depth=depth + 1,
                            parent_url=current_url,
                        )
                    )
                    continue
                if normalized_url in seen:
                    continue
                seen.add(normalized_url)
                queue.append((normalized_url, depth + 1, current_url))

        summary = ScanSummary(
            status=ScanStatus.COMPLETED,
            stop_reason=stop_reason,
            start_url=start_url,
            normalized_start_url=normalized_start_url,
            site_key=selected_site_key,
            max_depth=active_policy.max_depth,
            max_pages=active_policy.max_pages,
            max_runtime_seconds=active_policy.max_runtime_seconds,
            same_domain_only=active_policy.same_domain_only,
            per_host_concurrency=active_policy.per_host_concurrency,
            queued_url_count=len(seen),
            scanned_url_count=scanned_url_count,
            accepted_result_count=len(candidates_by_key),
            rejected_url_count=len(rejections),
            duration_ms=_duration_ms(started),
        )
        return ScanResult(summary=summary, candidates=tuple(candidates_by_key.values()), rejections=tuple(rejections))

    def _select_site_key(self, site_key: str, normalized_start_url: str | None) -> str:
        if site_key != "auto":
            return site_key
        if normalized_start_url and urlparse(normalized_start_url).netloc.lower() in PRINTABLES_HOSTS:
            return PrintablesAdapter.site_key
        return MetadataOnlyAdapter.site_key

    def _rejected_result(
        self,
        start_url: str,
        site_key: str,
        policy: CrawlPolicy,
        stop_reason: ScanStopReason,
        duration_ms: int,
        normalized_start_url: str | None = None,
        rejections: tuple[CrawlRejection, ...] | None = None,
    ) -> ScanResult:
        rejection_items = rejections or (
            CrawlRejection(source_url=start_url, reason=stop_reason.value.replace("_", " "), depth=0),
        )
        summary = ScanSummary(
            status=ScanStatus.REJECTED,
            stop_reason=stop_reason,
            start_url=start_url,
            normalized_start_url=normalized_start_url,
            site_key=site_key,
            max_depth=policy.max_depth,
            max_pages=policy.max_pages,
            max_runtime_seconds=policy.max_runtime_seconds,
            same_domain_only=policy.same_domain_only,
            per_host_concurrency=policy.per_host_concurrency,
            queued_url_count=0,
            scanned_url_count=0,
            accepted_result_count=0,
            rejected_url_count=len(rejection_items),
            duration_ms=duration_ms,
        )
        return ScanResult(summary=summary, candidates=(), rejections=rejection_items)


def _allowed_hosts(policy: CrawlPolicy, adapter: SiteScanAdapter, start_host: str) -> frozenset[str]:
    allowed_hosts = set(policy.allowed_hosts)
    allowed_hosts.update(adapter.allowed_hosts)
    allowed_hosts.add(start_host)
    return frozenset(host.lower() for host in allowed_hosts)


def _host_allowed(host: str, allowed_hosts: frozenset[str]) -> bool:
    host = host.lower()
    return host in allowed_hosts


def _duration_ms(started: float) -> int:
    return max(0, int((monotonic() - started) * 1000))


def _candidate_dedupe_key(site_key: str, candidate) -> tuple[str, str]:
    if candidate.external_model_id:
        return site_key, candidate.external_model_id
    return site_key, candidate.normalized_url


def _candidate_rank(candidate) -> tuple[int, float]:
    return candidate.depth, -candidate.confidence
