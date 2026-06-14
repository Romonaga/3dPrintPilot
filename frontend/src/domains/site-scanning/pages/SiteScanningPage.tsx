import { ScanForm } from "../components/ScanForm";
import { ScanLimitsPanel } from "../components/ScanLimitsPanel";
import { ScanMetrics } from "../components/ScanMetrics";
import { ScanResultsTable } from "../components/ScanResultsTable";
import { useSiteScan } from "../hooks/useSiteScan";

export default function SiteScanningPage() {
  const scan = useSiteScan();

  return (
    <section className="site-scan-layout" aria-label="Site scanning">
      <div className="site-scan-main">
        <section className="panel scan-source-panel" aria-labelledby="scan-source-title">
          <div className="panel-header">
            <h2 id="scan-source-title">Scan Source</h2>
          </div>
          <ScanForm
            isScanning={scan.isScanning}
            onSubmit={scan.runScan}
            onUrlChange={scan.setUrl}
            url={scan.url}
          />
          {scan.error ? <p className="error-text">{scan.error}</p> : null}
        </section>
        <ScanResultsTable result={scan.result} />
      </div>
      <aside className="site-scan-side">
        <ScanLimitsPanel limits={scan.limits} onChange={scan.setLimits} />
        <ScanMetrics summary={scan.result?.summary ?? null} />
      </aside>
    </section>
  );
}
