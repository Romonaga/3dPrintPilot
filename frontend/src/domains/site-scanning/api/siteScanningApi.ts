import { type SiteScanLimits, type SiteScanResult } from "../types";
import { apiFetch } from "../../../lib/apiFetch";

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
  });

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
      evidence: candidate.evidence
    })),
    rejections: result.rejections.map((rejection) => ({
      sourceUrl: rejection.source_url,
      reason: rejection.reason,
      depth: rejection.depth,
      parentUrl: rejection.parent_url
    }))
  };
}
