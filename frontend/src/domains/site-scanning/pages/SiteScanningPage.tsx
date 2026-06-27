import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { StatusBadge } from "../../../components/StatusBadge";
import { listSiteAdapters, updateSiteAdapter } from "../api/siteScanningApi";
import { ScanForm } from "../components/ScanForm";
import { ScanLimitsPanel } from "../components/ScanLimitsPanel";
import { ScanMetrics } from "../components/ScanMetrics";
import { ScanResultsTable } from "../components/ScanResultsTable";
import { useSiteScan } from "../hooks/useSiteScan";
import { SupportedSourceImportPanel } from "../../source-sites/components/SupportedSourceImportPanel";
import { type SourceProjectRequest } from "../../source-sites/hooks/useSupportedSourceImport";
import { type SiteAdapter, type SiteScanCandidate } from "../types";

export default function SiteScanningPage() {
  const scan = useSiteScan();
  const [adapters, setAdapters] = useState<SiteAdapter[]>([]);
  const [adapterError, setAdapterError] = useState<string | null>(null);
  const [sourceProjectRequest, setSourceProjectRequest] = useState<SourceProjectRequest | null>(null);
  const [savingAdapter, setSavingAdapter] = useState<string | null>(null);
  const importPanelRef = useRef<HTMLElement | null>(null);
  const importSiteKey = importableSiteKey(scan.result?.summary.siteKey ?? null, adapters);

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

  function handleImportCandidate(candidate: SiteScanCandidate) {
    if (!importSiteKey) {
      return;
    }
    setSourceProjectRequest({
      projectUrl: candidate.sourceUrl,
      requestId: Date.now(),
      siteKey: importSiteKey
    });
    requestAnimationFrame(() => {
      if (typeof importPanelRef.current?.scrollIntoView === "function") {
        importPanelRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
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
        <ScanResultsTable
          importSiteKey={importSiteKey}
          onImportCandidate={handleImportCandidate}
          result={scan.result}
        />
        <SupportedSourceImportPanel
          autoDiscoverProjectRequest
          className="panel scan-source-import-panel"
          heading="Import Candidate Files"
          headingId="scan-source-import-title"
          panelRef={importPanelRef}
          projectRequest={sourceProjectRequest}
          showImportedSummary
          siteKey={importSiteKey ?? undefined}
        />
      </div>
      <aside className="site-scan-side">
        <section className="panel adapter-panel" aria-labelledby="adapter-title">
          <div className="panel-header">
            <div>
              <h2 id="adapter-title">Adapters</h2>
              <p className="muted-copy">Enabled adapters can scan matching sites; disabled adapters are skipped.</p>
            </div>
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

function importableSiteKey(siteKey: string | null, adapters: SiteAdapter[]) {
  if (!siteKey) {
    return null;
  }
  const adapter = adapters.find((item) => item.siteKey === siteKey);
  if (!adapter || !adapter.enabled || adapter.supportLevel === "generic_only" || !adapter.supportsDownloads) {
    return null;
  }
  if (!adapter.capabilities.includes("file_listing") || !adapter.capabilities.includes("file_download")) {
    return null;
  }
  return adapter.siteKey;
}
