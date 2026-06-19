import { type SiteAdapter, type SiteScanLimits, type SiteScanResult } from "../types";
import { apiFetch } from "../../../lib/apiFetch";

type ApiAdapter = {
  site_key: string;
  display_name: string;
  enabled: boolean;
  supports_downloads: boolean;
  allowed_hosts: string[];
  default_limits: Record<string, unknown>;
  robots_terms_notes: string | null;
};

type ApiSummary = {
  scan_run_id: number | null;
  status: string;
  stop_reason: string;
  start_url: string;
  normalized_start_url: string | null;
  site_key: string;
  max_depth: number;
  max_pages: number;
  max_runtime_seconds: number;
  same_domain_only: boolean;
  per_host_concurrency: number;
  queued_url_count: number;
  scanned_url_count: number;
  accepted_result_count: number;
  rejected_url_count: number;
  duration_ms: number;
};

type ApiCandidate = {
  source_url: string;
  title: string;
  depth: number;
  parent_url: string | null;
  normalized_url: string;
  inclusion_reason: string;
  status: string;
  confidence: number;
  evidence: string[];
  license: string | null;
  attribution: string | null;
  requirements: Record<string, unknown>;
};

type ApiRejection = {
  source_url: string;
  reason: string;
  depth: number;
  parent_url: string | null;
};

type ApiResult = {
  summary: ApiSummary;
  candidates: ApiCandidate[];
  rejections: ApiRejection[];
};

export async function listSiteAdapters(): Promise<SiteAdapter[]> {
  const response = await apiFetch("/api/site-scanning/adapters");
  if (!response.ok) {
    throw new Error(`Adapter list failed with HTTP ${response.status}`);
  }
  const adapters = (await response.json()) as ApiAdapter[];
  return adapters.map(fromApiAdapter);
}

export async function updateSiteAdapter(siteKey: string, enabled: boolean): Promise<SiteAdapter> {
  const response = await apiFetch(`/api/site-scanning/adapters/${siteKey}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled })
  });
  if (!response.ok) {
    throw new Error(`Adapter update failed with HTTP ${response.status}`);
  }
  return fromApiAdapter((await response.json()) as ApiAdapter);
}

export async function createSiteScan(url: string, limits: SiteScanLimits): Promise<SiteScanResult> {
  const response = await apiFetch("/api/site-scanning/scans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      site_key: "auto",
      max_depth: limits.maxDepth,
      max_pages: limits.maxPages,
      max_runtime_seconds: limits.maxRuntimeSeconds,
      same_domain_only: limits.sameDomainOnly,
      per_host_concurrency: limits.perHostConcurrency
    })
  }, { timeoutMs: 60_000 });

  if (!response.ok) {
    throw new Error(`Scan failed with HTTP ${response.status}`);
  }

  return fromApi(await response.json());
}

function fromApi(result: ApiResult): SiteScanResult {
  return {
    summary: {
      scanRunId: result.summary.scan_run_id,
      status: result.summary.status,
      stopReason: result.summary.stop_reason,
      startUrl: result.summary.start_url,
      normalizedStartUrl: result.summary.normalized_start_url,
      siteKey: result.summary.site_key,
      maxDepth: result.summary.max_depth,
      maxPages: result.summary.max_pages,
      maxRuntimeSeconds: result.summary.max_runtime_seconds,
      sameDomainOnly: result.summary.same_domain_only,
      perHostConcurrency: result.summary.per_host_concurrency,
      queuedUrlCount: result.summary.queued_url_count,
      scannedUrlCount: result.summary.scanned_url_count,
      acceptedResultCount: result.summary.accepted_result_count,
      rejectedUrlCount: result.summary.rejected_url_count,
      durationMs: result.summary.duration_ms
    },
    candidates: result.candidates.map((candidate) => ({
      sourceUrl: candidate.source_url,
      title: candidate.title,
      depth: candidate.depth,
      parentUrl: candidate.parent_url,
      normalizedUrl: candidate.normalized_url,
      inclusionReason: candidate.inclusion_reason,
      status: candidate.status,
      confidence: candidate.confidence,
      evidence: candidate.evidence,
      license: candidate.license,
      attribution: candidate.attribution,
      requirements: candidate.requirements
    })),
    rejections: result.rejections.map((rejection) => ({
      sourceUrl: rejection.source_url,
      reason: rejection.reason,
      depth: rejection.depth,
      parentUrl: rejection.parent_url
    }))
  };
}

function fromApiAdapter(adapter: ApiAdapter): SiteAdapter {
  return {
    siteKey: adapter.site_key,
    displayName: adapter.display_name,
    enabled: adapter.enabled,
    supportsDownloads: adapter.supports_downloads,
    allowedHosts: adapter.allowed_hosts,
    defaultLimits: adapter.default_limits,
    robotsTermsNotes: adapter.robots_terms_notes
  };
}
