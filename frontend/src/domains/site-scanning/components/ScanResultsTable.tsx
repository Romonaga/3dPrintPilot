import { type SiteScanCandidate, type SiteScanResult } from "../types";
import { CandidateImportAction } from "./CandidateImportAction";
import { candidateStatusView } from "../utils/scanCandidateStatus";

type ScanResultsTableProps = {
  importSiteKey: string | null;
  onImportCandidate: (candidate: SiteScanCandidate) => void;
  result: SiteScanResult | null;
};

export function ScanResultsTable({ importSiteKey, onImportCandidate, result }: ScanResultsTableProps) {
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
              <th>Next Step</th>
              <th>Depth</th>
              <th>Confidence</th>
              <th>Attribution</th>
              <th>Action</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {(result?.candidates ?? []).map((candidate) => {
              const status = candidateStatusView(candidate.status);
              return (
                <tr key={candidate.normalizedUrl}>
                  <td>{candidate.title}</td>
                  <td>
                    <span className={`result-pill ${status.tone}`}>{status.label}</span>
                  </td>
                  <td className="scan-candidate-next">{status.nextStep}</td>
                  <td>{candidate.depth}</td>
                  <td>{Math.round(candidate.confidence * 100)}%</td>
                  <td>{candidate.attribution ?? candidate.license ?? "Unknown"}</td>
                  <td>
                    <CandidateImportAction
                      candidate={candidate}
                      importSiteKey={importSiteKey}
                      onImportCandidate={onImportCandidate}
                    />
                  </td>
                  <td>
                    <a href={candidate.sourceUrl} target="_blank" rel="noreferrer">
                      Open
                    </a>
                  </td>
                </tr>
              );
            })}
            {!result || result.candidates.length === 0 ? (
              <tr>
                <td colSpan={8}>No candidates yet.</td>
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
