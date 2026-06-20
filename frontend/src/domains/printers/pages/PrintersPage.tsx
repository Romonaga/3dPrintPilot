import { Radar, Trash2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { Spinner } from "../../../components/Spinner";
import { discoveredPrinterKey, type PrintersState } from "../hooks/usePrinters";

type PrintersPageProps = {
  autoStartScanRequestId?: number | null;
  onAutoStartScanConsumed?: () => void;
  printers: PrintersState;
};

export default function PrintersPage({
  autoStartScanRequestId = null,
  onAutoStartScanConsumed,
  printers
}: PrintersPageProps) {
  const consumedScanRequestId = useRef<number | null>(null);

  useEffect(() => {
    if (autoStartScanRequestId === null || consumedScanRequestId.current === autoStartScanRequestId) {
      return;
    }
    consumedScanRequestId.current = autoStartScanRequestId;
    onAutoStartScanConsumed?.();
    void printers.runScan();
  }, [autoStartScanRequestId, onAutoStartScanConsumed, printers]);

  return (
    <section className="printers-page" aria-label="Printers">
      <section className="panel printer-actions-panel" aria-labelledby="printer-actions-title">
        <div className="panel-header">
          <h2 id="printer-actions-title">Printer Actions</h2>
          <button className="primary-action icon-action" type="button" onClick={printers.runScan} disabled={printers.isScanning}>
            {printers.isScanning ? <Spinner size={16} /> : <Radar size={16} aria-hidden="true" />}
            <span>{printers.isScanning ? "Scanning" : "Scan LAN"}</span>
          </button>
        </div>
        {printers.error ? <p className="error-text">{printers.error}</p> : null}
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
          {printers.printers.map((printer) => (
            <article className="printer-row" key={printer.id}>
              <div>
                <h3>{printer.name}</h3>
                <p>
                  {printer.protocol}://{printer.host}:{printer.port}
                </p>
                <p>{formatBuildVolume(printer.buildVolumeXmm, printer.buildVolumeYmm, printer.buildVolumeZmm)}</p>
              </div>
              <div className="row-meta">
                <span>{printer.printerType}</span>
                <strong>{printer.state}</strong>
                <button
                  aria-label={`Remove ${printer.name}`}
                  className="icon-only-button"
                  type="button"
                  onClick={() => void printers.removePrinter(printer.id)}
                >
                  <Trash2 size={16} aria-hidden="true" />
                </button>
              </div>
            </article>
          ))}
          {!printers.isLoading && printers.printers.length === 0 ? <p className="empty-text">No saved printers yet.</p> : null}
        </div>
      </section>

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
              const primaryEndpointKey = primaryEndpoint ? discoveredPrinterKey(primaryEndpoint) : null;
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
                    {primaryEndpoint ? (
                      <button
                        className="text-button icon-action"
                        type="button"
                        onClick={() => void printers.addDiscoveredPrinter(primaryEndpoint)}
                        disabled={printers.isAdding}
                      >
                        {printers.addingAction === primaryEndpointKey ? <Spinner size={14} /> : null}
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
                    </div>
                    <div className="row-meta">
                      <span>{printer.serviceType}</span>
                      <strong>{printer.confidence}%</strong>
                      <button
                        className="text-button icon-action"
                        type="button"
                        onClick={() => void printers.addDiscoveredPrinter(printer)}
                        disabled={printers.isAdding}
                      >
                        {printers.addingAction === discoveredPrinterKey(printer) ? <Spinner size={14} /> : null}
                        <span>Confirm</span>
                      </button>
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
