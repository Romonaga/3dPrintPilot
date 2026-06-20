import { type CompatibilityCheck } from "../../dashboard/types";

type CompatibilitySummaryProps = {
  checks: CompatibilityCheck[];
};

export function CompatibilitySummary({ checks }: CompatibilitySummaryProps) {
  return (
    <section className="panel compatibility-panel" aria-labelledby="compatibility-title">
      <div className="panel-header">
        <h2 id="compatibility-title">Compatibility</h2>
        <button className="text-button" type="button">
          Upload Model
        </button>
      </div>
      {checks.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>Printer</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {checks.map((check) => (
              <tr key={check.id}>
                <td>{check.model}</td>
                <td>{check.printer}</td>
                <td>
                  <span className={`result-pill ${check.tone}`}>{check.result}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="empty-text">No compatibility checks yet.</p>
      )}
    </section>
  );
}
