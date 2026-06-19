import { RefreshCw, ScanSearch } from "lucide-react";
import { FormEvent, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { useCompatibilityChecks } from "../hooks/useCompatibilityChecks";
import { type CompatibilityCheckResult } from "../types";

export default function CompatibilityPage() {
  const compatibility = useCompatibilityChecks();
  const [scanRunId, setScanRunId] = useState("");
  const [maxCandidates, setMaxCandidates] = useState(10);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await compatibility.run(Number(scanRunId), maxCandidates);
  }

  return (
    <section className="compatibility-page">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>Run Compatibility</h2>
            {compatibility.error ? <p className="form-error">{compatibility.error}</p> : null}
          </div>
          <button className="text-button icon-action" type="button" onClick={compatibility.reload} disabled={compatibility.isLoading}>
            {compatibility.isLoading ? <Spinner size={15} /> : <RefreshCw size={15} aria-hidden="true" />}
            <span>Refresh</span>
          </button>
        </div>

        <form className="compatibility-form" onSubmit={handleSubmit}>
          <label className="field-label">
            Site scan run ID
            <input
              min={1}
              onChange={(event) => setScanRunId(event.target.value)}
              required
              type="number"
              value={scanRunId}
            />
          </label>
          <label className="field-label">
            Max candidates
            <input
              max={100}
              min={1}
              onChange={(event) => setMaxCandidates(Number(event.target.value))}
              type="number"
              value={maxCandidates}
            />
          </label>
          <button className="primary-action icon-action" disabled={compatibility.isRunning} type="submit">
            {compatibility.isRunning ? <Spinner size={15} /> : <ScanSearch size={15} aria-hidden="true" />}
            <span>{compatibility.isRunning ? "Checking" : "Run Checks"}</span>
          </button>
        </form>

        {compatibility.lastRun ? (
          <dl className="metric-grid compatibility-run-metrics">
            <div>
              <dt>Candidates</dt>
              <dd>{compatibility.lastRun.candidateCount}</dd>
            </div>
            <div>
              <dt>Printers</dt>
              <dd>{compatibility.lastRun.printerCount}</dd>
            </div>
            <div>
              <dt>Checks</dt>
              <dd>{compatibility.lastRun.checkCount}</dd>
            </div>
            <div>
              <dt>Run ID</dt>
              <dd>{compatibility.lastRun.scanRunId}</dd>
            </div>
          </dl>
        ) : null}
      </article>

      <article className="panel">
        <div className="panel-header">
          <h2>Compatibility Results</h2>
          <span className="status-badge muted">{compatibility.isLoading ? "Loading" : `${compatibility.checks.length} checks`}</span>
        </div>
        <div className="compatibility-results">
          {compatibility.checks.map((check) => (
            <CompatibilityResult key={check.id} check={check} />
          ))}
          {!compatibility.isLoading && compatibility.checks.length === 0 ? (
            <p className="empty-text">No compatibility checks have been stored yet.</p>
          ) : null}
        </div>
      </article>
    </section>
  );
}

function CompatibilityResult({ check }: { check: CompatibilityCheckResult }) {
  return (
    <article className="compatibility-result">
      <div className="compatibility-result-header">
        <div>
          <h3>{check.modelTitle}</h3>
          <p>{check.printerName}</p>
        </div>
        <span className={`result-pill ${resultTone(check.status)}`}>{resultLabel(check.status)}</span>
      </div>
      <p>
        {check.sourceType.replace("_", " ")} · {check.confidenceLabel} confidence
      </p>
      <ul className="compatibility-item-list">
        {check.items.map((item) => (
          <li key={`${check.id}-${item.code}`}>
            <strong>{item.code.replace("_", " ")}</strong>
            <span className={`result-pill ${resultTone(item.severity)}`}>{item.severity}</span>
            <p>{item.message}</p>
          </li>
        ))}
      </ul>
    </article>
  );
}

function resultTone(status: string) {
  if (status === "pass") {
    return "ok";
  }
  if (status === "fail") {
    return "bad";
  }
  return "warn";
}

function resultLabel(status: string) {
  if (status === "pass") {
    return "compatible";
  }
  if (status === "fail") {
    return "not compatible";
  }
  return "maybe";
}
