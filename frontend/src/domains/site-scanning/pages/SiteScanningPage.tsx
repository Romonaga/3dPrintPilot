import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { StatusBadge } from "../../../components/StatusBadge";
import { listSiteAdapters, updateSiteAdapter } from "../api/siteScanningApi";
import { ScanForm } from "../components/ScanForm";
import { ScanLimitsPanel } from "../components/ScanLimitsPanel";
import { ScanMetrics } from "../components/ScanMetrics";
import { ScanResultsTable } from "../components/ScanResultsTable";
import { useSiteScan } from "../hooks/useSiteScan";
import { type SiteAdapter } from "../types";

export default function SiteScanningPage() {
  const scan = useSiteScan();
  const [adapters, setAdapters] = useState<SiteAdapter[]>([]);
  const [adapterError, setAdapterError] = useState<string | null>(null);
  const [savingAdapter, setSavingAdapter] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listSiteAdapters()
      .then((items) => {
        if (active) {
          setAdapters(items);
          setAdapterError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setAdapterError(err instanceof Error ? err.message : "Adapter list failed");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleAdapterToggle(adapter: SiteAdapter) {
    setSavingAdapter(adapter.siteKey);
    try {
      const updated = await updateSiteAdapter(adapter.siteKey, !adapter.enabled);
      setAdapters((items) => items.map((item) => (item.siteKey === updated.siteKey ? updated : item)));
      setAdapterError(null);
    } catch (err) {
      setAdapterError(err instanceof Error ? err.message : "Adapter update failed");
    } finally {
      setSavingAdapter(null);
    }
  }

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
        <section className="panel adapter-panel" aria-labelledby="adapter-title">
          <div className="panel-header">
            <h2 id="adapter-title">Adapters</h2>
          </div>
          <div className="adapter-list">
            {adapters.map((adapter) => (
              <article className="adapter-row" key={adapter.siteKey}>
                <div>
                  <h3>{adapter.displayName}</h3>
                  <p>{adapter.robotsTermsNotes ?? "Public metadata only."}</p>
                </div>
                <div className="adapter-actions">
                  <StatusBadge
                    icon={adapter.enabled ? CheckCircle2 : AlertTriangle}
                    label={adapter.enabled ? "Enabled" : "Disabled"}
                    tone={adapter.enabled ? "ok" : "warn"}
                  />
                  <button
                    className="text-button"
                    type="button"
                    disabled={savingAdapter === adapter.siteKey}
                    onClick={() => handleAdapterToggle(adapter)}
                  >
                    {savingAdapter === adapter.siteKey ? <Spinner size={14} /> : null}
                    <span>{adapter.enabled ? "Disable" : "Enable"}</span>
                  </button>
                </div>
              </article>
            ))}
          </div>
          {adapterError ? <p className="error-text">{adapterError}</p> : null}
        </section>
        <ScanLimitsPanel limits={scan.limits} onChange={scan.setLimits} />
        <ScanMetrics summary={scan.result?.summary ?? null} />
      </aside>
    </section>
  );
}
