import { type PrinterSummary } from "../../dashboard/types";

type PrinterInventoryProps = {
  onScanLan: () => void;
  printers: PrinterSummary[];
};

export function PrinterInventory({ onScanLan, printers }: PrinterInventoryProps) {
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
          printers.map((printer) => (
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
              {printer.progressPercent !== null ? (
                <div className="dashboard-printer-progress">
                  <progress aria-label={`Print progress for ${printer.name}`} max={100} value={printer.progressPercent} />
                  <span>{printer.progressLabel}</span>
                </div>
              ) : null}
            </article>
          ))
        ) : (
          <p className="empty-text">No saved printers yet. Scan LAN to discover printers.</p>
        )}
      </div>
    </section>
  );
}
