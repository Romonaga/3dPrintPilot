export type SiteScanLimits = {
  maxDepth: number;
  maxPages: number;
  maxRuntimeSeconds: number;
  sameDomainOnly: boolean;
  perHostConcurrency: number;
};

export type SiteAdapter = {
  siteKey: string;
  displayName: string;
  enabled: boolean;
  supportsDownloads: boolean;
  allowedHosts: string[];
  defaultLimits: Record<string, unknown>;
  robotsTermsNotes: string | null;
};

export type SiteScanSummary = {
  scanRunId: number | null;
  status: string;
  stopReason: string;
  startUrl: string;
  normalizedStartUrl: string | null;
  siteKey: string;
  maxDepth: number;
  maxPages: number;
  maxRuntimeSeconds: number;
  sameDomainOnly: boolean;
  perHostConcurrency: number;
  queuedUrlCount: number;
  scannedUrlCount: number;
  acceptedResultCount: number;
  rejectedUrlCount: number;
  durationMs: number;
};

export type SiteScanCandidate = {
  sourceUrl: string;
  title: string;
  depth: number;
  parentUrl: string | null;
  normalizedUrl: string;
  inclusionReason: string;
  status: string;
  confidence: number;
  evidence: string[];
  license: string | null;
  attribution: string | null;
  requirements: Record<string, unknown>;
};

export type SiteScanRejection = {
  sourceUrl: string;
  reason: string;
  depth: number;
  parentUrl: string | null;
};

export type SiteScanResult = {
  summary: SiteScanSummary;
  candidates: SiteScanCandidate[];
  rejections: SiteScanRejection[];
};
