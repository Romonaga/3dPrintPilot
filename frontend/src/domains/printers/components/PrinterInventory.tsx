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
        {printers.map((printer) => (
          <article className="printer-row" key={printer.id}>
            <div>
              <h3>{printer.name}</h3>
              <p>{printer.buildVolume}</p>
            </div>
            <div className="row-meta">
              <span>{printer.state}</span>
              <strong>{printer.confidence}%</strong>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
