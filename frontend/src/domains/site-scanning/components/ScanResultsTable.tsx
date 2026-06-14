import { type SiteScanResult } from "../types";

type ScanResultsTableProps = {
  result: SiteScanResult | null;
};

export function ScanResultsTable({ result }: ScanResultsTableProps) {
  return (
    <section className="panel scan-results-panel" aria-labelledby="scan-results-title">
      <div className="panel-header">
        <h2 id="scan-results-title">Candidates</h2>
        <span className="status-badge muted">{result?.candidates.length ?? 0} found</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Status</th>
              <th>Depth</th>
              <th>Confidence</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {(result?.candidates ?? []).map((candidate) => (
              <tr key={candidate.normalizedUrl}>
                <td>{candidate.title}</td>
                <td>
                  <span className="result-pill warn">{candidate.status}</span>
                </td>
                <td>{candidate.depth}</td>
                <td>{Math.round(candidate.confidence * 100)}%</td>
                <td>
                  <a href={candidate.sourceUrl} target="_blank" rel="noreferrer">
                    Open
                  </a>
                </td>
              </tr>
            ))}
            {!result || result.candidates.length === 0 ? (
              <tr>
                <td colSpan={5}>No candidates yet.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {result && result.rejections.length > 0 ? (
        <div className="scan-rejections" aria-label="Rejected URLs">
          {result.rejections.map((rejection) => (
            <p key={`${rejection.sourceUrl}-${rejection.reason}`}>
              {rejection.reason}: {rejection.sourceUrl}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}
