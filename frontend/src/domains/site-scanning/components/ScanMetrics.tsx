import { type SiteScanSummary } from "../types";

type ScanMetricsProps = {
  summary: SiteScanSummary | null;
};

const emptySummary = {
  scanRunId: null,
  status: "ready",
  stopReason: "not_started",
  queuedUrlCount: 0,
  scannedUrlCount: 0,
  acceptedResultCount: 0,
  rejectedUrlCount: 0,
  durationMs: 0
};

export function ScanMetrics({ summary }: ScanMetricsProps) {
  const metrics = summary ?? emptySummary;

  return (
    <section className="panel scan-metrics-panel" aria-labelledby="scan-metrics-title">
      <div className="panel-header">
        <h2 id="scan-metrics-title">Scan Metrics</h2>
        <span className="status-badge muted">{metrics.status}</span>
      </div>
      <dl className="metric-grid">
        <div>
          <dt>Queued</dt>
          <dd>{metrics.queuedUrlCount}</dd>
        </div>
        <div>
          <dt>Scanned</dt>
          <dd>{metrics.scannedUrlCount}</dd>
        </div>
        <div>
          <dt>Accepted</dt>
          <dd>{metrics.acceptedResultCount}</dd>
        </div>
        <div>
          <dt>Rejected</dt>
          <dd>{metrics.rejectedUrlCount}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{metrics.durationMs} ms</dd>
        </div>
        <div>
          <dt>Stop</dt>
          <dd>{metrics.stopReason}</dd>
        </div>
        <div>
          <dt>Run ID</dt>
          <dd>{metrics.scanRunId ?? "-"}</dd>
        </div>
      </dl>
    </section>
  );
}
