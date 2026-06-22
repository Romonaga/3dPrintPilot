import { Wrench } from "lucide-react";
import { useMemo, useState } from "react";
import { PrinterCapabilitySummary } from "../../printers/components/PrinterCapabilitySummary";
import { PrinterControlPanel, supportsMoonrakerControl } from "../../printers/components/PrinterControlPanel";
import { type Printer } from "../../printers/types";
import { type PrinterSummary } from "../types";

type PrinterInventoryProps = {
  onScanLan: () => void;
  printerRecords: Printer[];
  printers: PrinterSummary[];
};

export function PrinterInventory({ onScanLan, printerRecords, printers }: PrinterInventoryProps) {
  const [expandedPrinterId, setExpandedPrinterId] = useState<string | null>(null);
  const printerRecordById = useMemo(
    () => new Map(printerRecords.map((printer) => [String(printer.id), printer])),
    [printerRecords]
  );

  return (
    <section className="panel printer-panel" aria-labelledby="printer-panel-title">
      <div className="panel-header">
        <h2 id="printer-panel-title">Printers</h2>
        <button type="button" className="text-button" onClick={onScanLan}>
          Scan LAN
        </button>
      </div>
      <div className="printer-list">
        {printers.length > 0 ? (
          printers.map((printer) => {
            const printerRecord = printerRecordById.get(printer.id);
            const controlsAvailable = printerRecord ? supportsMoonrakerControl(printerRecord) : false;
            const controlsExpanded = expandedPrinterId === printer.id;

            return (
              <article className="printer-row" key={printer.id}>
                <div className="printer-row-main">
                  <div>
                    <h3>{printer.name}</h3>
                    <p>{printer.buildVolume}</p>
                  </div>
                  <div className="row-meta printer-dashboard-meta">
                    <span className={`printer-state-pill ${printer.availabilityTone}`}>{printer.availabilityLabel}</span>
                    <strong>{printer.jobStatusLabel}</strong>
                  </div>
                </div>
                {printerRecord ? (
                  <PrinterCapabilitySummary
                    ariaLabel={`Capabilities for ${printer.name}`}
                    emptyLabel="Capabilities unknown"
                    printer={printerRecord}
                  />
                ) : null}
                {printer.progressPercent !== null ? (
                  <div className="dashboard-printer-progress">
                    <progress aria-label={`Print progress for ${printer.name}`} max={100} value={printer.progressPercent} />
                    <span>{printer.progressLabel}</span>
                  </div>
                ) : null}
                {controlsAvailable && printerRecord ? (
                  <div className="dashboard-printer-controls">
                    <button
                      aria-controls={`dashboard-printer-controls-${printer.id}`}
                      aria-expanded={controlsExpanded}
                      aria-label={`${controlsExpanded ? "Hide controls" : "Show controls"} for ${printer.name}`}
                      className="text-button icon-action"
                      onClick={() => setExpandedPrinterId(controlsExpanded ? null : printer.id)}
                      type="button"
                    >
                      <Wrench size={15} aria-hidden="true" />
                      <span>{controlsExpanded ? "Hide controls" : "Show controls"}</span>
                    </button>
                    {controlsExpanded ? (
                      <div id={`dashboard-printer-controls-${printer.id}`}>
                        <PrinterControlPanel printer={printerRecord} />
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </article>
            );
          })
        ) : (
          <p className="empty-text">No saved printers yet. Scan LAN to discover printers.</p>
        )}
      </div>
    </section>
  );
}
