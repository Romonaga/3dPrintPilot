import { Radar, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { refreshPrinterEngines } from "../api/printersApi";
import { PrinterCapabilitySummary } from "../components/PrinterCapabilitySummary";
import { discoveredPrinterKey, type PrinterRefreshInfo, type PrintersState } from "../hooks/usePrinters";

type PrintersPageProps = {
  autoStartScanRequestId?: number | null;
  onAutoStartScanConsumed?: () => void;
  printers: PrintersState;
};

type PrinterContextMenuState = {
  printerId: number;
  printerName: string;
  x: number;
  y: number;
};

export default function PrintersPage({
  autoStartScanRequestId = null,
  onAutoStartScanConsumed,
  printers
}: PrintersPageProps) {
  const consumedScanRequestId = useRef<number | null>(null);
  const [contextMenu, setContextMenu] = useState<PrinterContextMenuState | null>(null);
  const [engineRefreshPending, setEngineRefreshPending] = useState(false);
  const [engineRefreshMessage, setEngineRefreshMessage] = useState<string | null>(null);

  useEffect(() => {
    if (autoStartScanRequestId === null || consumedScanRequestId.current === autoStartScanRequestId) {
      return;
    }
    consumedScanRequestId.current = autoStartScanRequestId;
    onAutoStartScanConsumed?.();
    void printers.runScan();
  }, [autoStartScanRequestId, onAutoStartScanConsumed, printers]);

  useEffect(() => {
    if (contextMenu === null) {
      return;
    }

    const closeContextMenu = () => setContextMenu(null);
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeContextMenu();
      }
    };

    window.addEventListener("click", closeContextMenu);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("click", closeContextMenu);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [contextMenu]);

  useEffect(() => {
    if (contextMenu === null) {
      return;
    }

    if (!printers.printers.some((printer) => printer.id === contextMenu.printerId)) {
      setContextMenu(null);
    }
  }, [contextMenu, printers.printers]);

  async function handleEngineRefresh() {
    setEngineRefreshPending(true);
    setEngineRefreshMessage(null);
    try {
      const engines = await refreshPrinterEngines();
      setEngineRefreshMessage(`Engine catalog refreshed: ${engines.length} active`);
    } catch (refreshError) {
      setEngineRefreshMessage(refreshError instanceof Error ? refreshError.message : "Engine catalog refresh failed");
    } finally {
      setEngineRefreshPending(false);
    }
  }

  return (
    <section className="printers-page" aria-label="Printers">
      <section className="panel printer-actions-panel" aria-labelledby="printer-actions-title">
        <div className="panel-header">
          <h2 id="printer-actions-title">Printer Actions</h2>
          <div className="printer-actions-header-buttons">
            <button
              className="text-button icon-action"
              disabled={engineRefreshPending}
              onClick={() => void handleEngineRefresh()}
              type="button"
            >
              {engineRefreshPending ? <Spinner size={16} /> : <RefreshCw size={16} aria-hidden="true" />}
              <span>Refresh engines</span>
            </button>
            <button className="primary-action icon-action" type="button" onClick={printers.runScan} disabled={printers.isScanning}>
              {printers.isScanning ? <Spinner size={16} /> : <Radar size={16} aria-hidden="true" />}
              <span>{printers.isScanning ? "Scanning" : "Scan LAN"}</span>
            </button>
          </div>
        </div>
        {printers.error ? <p className="error-text">{printers.error}</p> : null}
        {engineRefreshMessage ? <p className="muted-copy">{engineRefreshMessage}</p> : null}
        <div className="printer-scan-settings">
          <label className="field-label">
            <span>Method</span>
            <select
              value={printers.scanSettings.scanMethod}
              onChange={(event) =>
                printers.setScanSettings({
                  ...printers.scanSettings,
                  scanMethod: event.target.value as "combined" | "mdns" | "http_probe"
                })
              }
            >
              <option value="combined">Combined</option>
              <option value="mdns">mDNS</option>
              <option value="http_probe">HTTP probe</option>
            </select>
          </label>
          <label className="field-label">
            <span>CIDR</span>
            <input
              value={printers.scanSettings.targetCidr}
              onChange={(event) => printers.setScanSettings({ ...printers.scanSettings, targetCidr: event.target.value })}
              placeholder="Auto /24"
            />
          </label>
          <label className="field-label">
            <span>Max hosts</span>
            <input
              type="number"
              min={1}
              max={512}
              value={printers.scanSettings.maxHosts}
              onChange={(event) => printers.setScanSettings({ ...printers.scanSettings, maxHosts: Number(event.target.value) })}
            />
          </label>
          <label className="field-label">
            <span>Ports</span>
            <input
              value={printers.scanSettings.ports}
              onChange={(event) => printers.setScanSettings({ ...printers.scanSettings, ports: event.target.value })}
            />
          </label>
        </div>
        {printers.scanResult ? (
          <dl className="metric-grid">
            <div>
              <dt>Run ID</dt>
              <dd>{printers.scanResult.summary.scanRunId}</dd>
            </div>
            <div>
              <dt>Found</dt>
              <dd>{printers.scanResult.summary.discoveredCount}</dd>
            </div>
            <div>
              <dt>Duration</dt>
              <dd>{printers.scanResult.summary.durationMs} ms</dd>
            </div>
            <div>
              <dt>Method</dt>
              <dd>{printers.scanResult.summary.method}</dd>
            </div>
            <div>
              <dt>Hosts</dt>
              <dd>{printers.scanResult.summary.scannedHostCount}</dd>
            </div>
            <div>
              <dt>Probes</dt>
              <dd>{printers.scanResult.summary.probeCount}</dd>
            </div>
          </dl>
        ) : null}
      </section>

      <section className="panel printer-list-panel" aria-labelledby="printer-list-title">
        <div className="panel-header">
          <h2 id="printer-list-title">Saved Printers</h2>
          <span className="status-badge muted">{printers.isLoading ? "Loading" : `${printers.printers.length} saved`}</span>
        </div>
        <div className="printer-list">
          {printers.printers.map((printer) => {
            const refreshInfo = printers.printerRefreshInfo[printer.id] ?? null;
            const refreshError = printers.printerRefreshErrors[printer.id] ?? null;
            const isRefreshing = printers.refreshingPrinterIds.has(printer.id);
            return (
              <article
                aria-label={`Saved printer ${printer.name}`}
                className="printer-row printer-known-row"
                key={printer.id}
                onContextMenu={(event) => {
                  event.preventDefault();
                  setContextMenu({
                    printerId: printer.id,
                    printerName: printer.name,
                    x: Math.max(8, Math.min(event.clientX, window.innerWidth - 220)),
                    y: Math.max(8, Math.min(event.clientY, window.innerHeight - 96))
                  });
                }}
              >
                <div className="printer-row-main">
                  <div>
                    <h3>{printer.name}</h3>
                    <p>
                      {printer.protocol}://{printer.host}:{printer.port}
                    </p>
                    <p>{formatBuildVolume(printer.buildVolumeXmm, printer.buildVolumeYmm, printer.buildVolumeZmm)}</p>
                    <PrinterCapabilitySummary
                      ariaLabel={`Capabilities for ${printer.name}`}
                      emptyLabel="Capabilities unknown"
                      printer={printer}
                    />
                    {refreshInfo ? <PrinterRefreshSummary refreshInfo={refreshInfo} /> : null}
                    {refreshError ? <p className="printer-refresh-error">{refreshError}</p> : null}
                  </div>
                  <div className="row-meta">
                    <span>{printer.printerType}</span>
                    <strong>{refreshInfo?.status.state ?? printer.state}</strong>
                    <div className="printer-card-actions">
                      <button
                        aria-label={`Refresh ${printer.name}`}
                        className="icon-only-button"
                        disabled={isRefreshing}
                        onClick={() => void printers.refreshPrinterInfo(printer.id)}
                        title="Refresh printer info"
                        type="button"
                      >
                        {isRefreshing ? <Spinner size={14} /> : <RefreshCw size={16} aria-hidden="true" />}
                      </button>
                      <button
                        aria-label={`Remove ${printer.name}`}
                        className="icon-only-button"
                        type="button"
                        onClick={() => void printers.removePrinter(printer.id)}
                      >
                        <Trash2 size={16} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
          {!printers.isLoading && printers.printers.length === 0 ? <p className="empty-text">No saved printers yet.</p> : null}
        </div>
      </section>

      {contextMenu ? (
        <div
          aria-label={`Actions for ${contextMenu.printerName}`}
          className="printer-context-menu"
          onClick={(event) => event.stopPropagation()}
          role="menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            className="printer-context-menu-item"
            onClick={() => {
              const printerId = contextMenu.printerId;
              setContextMenu(null);
              void printers.removePrinter(printerId);
            }}
            role="menuitem"
            type="button"
          >
            <Trash2 size={14} aria-hidden="true" />
            <span>Remove printer</span>
          </button>
        </div>
      ) : null}

      {printers.scanResult ? (
        <section className="panel discovered-printers-panel" aria-labelledby="discovered-printers-title">
          <div className="panel-header">
            <h2 id="discovered-printers-title">Discovered Devices</h2>
            <span className="status-badge muted">
              {printers.scanResult.groups.length} devices / {printers.scanResult.printers.length} endpoints
            </span>
          </div>
          <div className="printer-list">
            {printers.scanResult.groups.map((group) => {
              const primaryEndpoint = group.endpoints[0];
              const confirmEndpoint = primaryEndpoint
                ? { ...primaryEndpoint, identityKey: group.identityKey ?? primaryEndpoint.identityKey }
                : null;
              const confirmEndpointKey = confirmEndpoint ? discoveredPrinterKey(confirmEndpoint) : null;
              return (
                <article className="printer-row printer-group-row" key={group.host}>
                  <div className="printer-group-main">
                    <div>
                      <h3>{group.name}</h3>
                      <p>
                        {group.host} - {group.inferredType} - Ports {formatPorts(group.ports)}
                      </p>
                    </div>
                    <div className="capability-list" aria-label={`Capabilities for ${group.host}`}>
                      {group.capabilities.map((capability) => (
                        <span className="capability-pill" key={capability}>
                          {capability}
                        </span>
                      ))}
                    </div>
                    {primaryEndpoint ? (
                      <PrinterCapabilitySummary
                        ariaLabel={`Detected hardware capabilities for ${group.host}`}
                        includeBuildVolume
                        printer={primaryEndpoint}
                      />
                    ) : null}
                    <div className="endpoint-list" aria-label={`Detected endpoints for ${group.host}`}>
                      {group.endpoints.map((endpoint) => (
                        <div className="endpoint-row" key={`${endpoint.host}:${endpoint.port}:${endpoint.serviceType}`}>
                          <span>{formatEndpoint(endpoint.protocol, endpoint.host, endpoint.port)}</span>
                          <span>{endpoint.serviceType}</span>
                          <strong>{endpoint.confidence}%</strong>
                        </div>
                      ))}
                    </div>
                    <div className="capability-list" aria-label={`Evidence for ${group.host}`}>
                      {group.endpoints.flatMap((endpoint) => endpoint.evidence).map((evidence) => (
                        <span className="capability-pill" key={evidence}>
                          {evidence}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="row-meta">
                    <span>{group.inferredType}</span>
                    <strong>{group.confidence}%</strong>
                    {group.matchedPrinterId ? (
                      <span className="status-badge ok">Known</span>
                    ) : confirmEndpoint ? (
                      <button
                        className="text-button icon-action"
                        type="button"
                        onClick={() => void printers.addDiscoveredPrinter(confirmEndpoint)}
                        disabled={printers.isAdding}
                      >
                        {printers.addingAction === confirmEndpointKey ? <Spinner size={14} /> : null}
                        <span>Confirm</span>
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
            {printers.scanResult.groups.length === 0 && printers.scanResult.printers.length > 0
              ? printers.scanResult.printers.map((printer) => (
                  <article className="printer-row" key={discoveredPrinterKey(printer)}>
                    <div>
                      <h3>{printer.name}</h3>
                      <p>{formatEndpoint(printer.protocol, printer.host, printer.port)}</p>
                      <PrinterCapabilitySummary
                        ariaLabel={`Detected hardware capabilities for ${printer.name}`}
                        includeBuildVolume
                        printer={printer}
                      />
                    </div>
                    <div className="row-meta">
                      <span>{printer.serviceType}</span>
                      <strong>{printer.confidence}%</strong>
                      {printer.matchedPrinterId ? (
                        <span className="status-badge ok">Known</span>
                      ) : (
                        <button
                          className="text-button icon-action"
                          type="button"
                          onClick={() => void printers.addDiscoveredPrinter(printer)}
                          disabled={printers.isAdding}
                        >
                          {printers.addingAction === discoveredPrinterKey(printer) ? <Spinner size={14} /> : null}
                          <span>Confirm</span>
                        </button>
                      )}
                    </div>
                  </article>
                ))
              : null}
            {printers.scanResult.printers.length === 0 ? <p className="empty-text">No printer services found in this scan.</p> : null}
          </div>
        </section>
      ) : null}
    </section>
  );
}

function formatEndpoint(protocol: string, host: string, port: number) {
  return `${protocol}://${host}:${port}`;
}

function PrinterRefreshSummary({ refreshInfo }: { refreshInfo: PrinterRefreshInfo }) {
  const jobLabel = formatJobLabel(refreshInfo);
  const filamentLabels = formatFilamentLabels(refreshInfo);
  const diagnosticLabel = formatDiagnosticLabel(refreshInfo);
  return (
    <div className="printer-refresh-summary" aria-label="Refreshed printer info">
      <span>State: {refreshInfo.status.state}</span>
      {jobLabel ? <span>{jobLabel}</span> : null}
      {filamentLabels.map((label) => (
        <span key={label}>{label}</span>
      ))}
      {diagnosticLabel ? <span>{diagnosticLabel}</span> : null}
    </div>
  );
}

function formatJobLabel(refreshInfo: PrinterRefreshInfo) {
  const jobStatus = refreshInfo.jobStatus;
  if (!jobStatus) {
    return null;
  }
  const progress = formatProgressPercent(jobStatus.progress);
  const filename = jobStatus.filename ? ` - ${jobStatus.filename}` : "";
  return progress === null ? `Job: ${jobStatus.state}${filename}` : `Job: ${jobStatus.state}${filename} (${progress}%)`;
}

function formatFilamentLabels(refreshInfo: PrinterRefreshInfo) {
  return (refreshInfo.jobStatus?.toolheads ?? [])
    .map((toolhead) => {
      const material = [toolhead.material, toolhead.vendor, toolhead.subtype].filter(Boolean).join(" / ");
      if (material && toolhead.color) {
        return `${toolhead.label}: ${material} ${toolhead.color}`;
      }
      if (material) {
        return `${toolhead.label}: ${material}`;
      }
      if (toolhead.color) {
        return `${toolhead.label}: ${toolhead.color}`;
      }
      return null;
    })
    .filter((label): label is string => label !== null);
}

function formatDiagnosticLabel(refreshInfo: PrinterRefreshInfo) {
  const diagnostics = refreshInfo.capabilityDiagnostics;
  if (!diagnostics) {
    return null;
  }
  const agentCount = diagnostics.extensionAgents.length;
  const spoolman = diagnostics.spoolmanAvailable ? "Spoolman available" : "Spoolman unavailable";
  return `${agentCount} extension agents / ${spoolman}`;
}

function formatProgressPercent(progress: number | null | undefined) {
  if (typeof progress !== "number" || !Number.isFinite(progress)) {
    return null;
  }
  const normalized = progress <= 1 ? progress * 100 : progress;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function formatPorts(ports: number[]) {
  if (ports.length === 0) {
    return "unknown";
  }
  return ports.join(", ");
}

function formatBuildVolume(x: number | null, y: number | null, z: number | null) {
  if (!x || !y || !z) {
    return "Build volume unknown";
  }
  return `${x} x ${y} x ${z} mm`;
}
