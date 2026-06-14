import { AlertTriangle, CheckCircle2, RefreshCw, ShieldCheck } from "lucide-react";
import { FormEvent, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAiAccounting } from "../hooks/useAiAccounting";

const defaultEndDate = new Date().toISOString().slice(0, 10);
const defaultStartDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

export default function AiUsagePage() {
  const { status, runs, latestResult, isLoading, isReconciling, error, reload, reconcile } = useAiAccounting();
  const [periodStart, setPeriodStart] = useState(defaultStartDate);
  const [periodEnd, setPeriodEnd] = useState(defaultEndDate);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await reconcile(periodStart, periodEnd);
  }

  const accountKeyReady = status?.openAiAccountKeyConfigured ?? false;

  return (
    <section className="ai-usage-page">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>OpenAI Cost Reconciliation</h2>
            {error ? <p className="form-error">{error}</p> : null}
          </div>
          <button className="text-button icon-action" type="button" onClick={reload} disabled={isLoading}>
            {isLoading ? <Spinner size={15} /> : <RefreshCw size={15} aria-hidden="true" />}
            <span>Refresh</span>
          </button>
        </div>

        <div className="secret-status accounting-status">
          <StatusBadge
            icon={accountKeyReady ? CheckCircle2 : AlertTriangle}
            label={accountKeyReady ? "Account Key Ready" : "Account Key Missing"}
            tone={accountKeyReady ? "ok" : "warn"}
          />
          <StatusBadge
            icon={status?.openAiApiTokenConfigured ? CheckCircle2 : AlertTriangle}
            label={status?.openAiApiTokenConfigured ? "API Token Ready" : "API Token Missing"}
            tone={status?.openAiApiTokenConfigured ? "ok" : "warn"}
          />
          <span>{status?.reusablePackage ?? "local_ai_accounting"}</span>
        </div>

        <form className="reconciliation-form" onSubmit={handleSubmit}>
          <label className="field-label">
            Start
            <input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
          </label>
          <label className="field-label">
            End
            <input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
          </label>
          <button className="primary-action icon-action" type="submit" disabled={isReconciling || !accountKeyReady}>
            {isReconciling ? <Spinner size={15} /> : <ShieldCheck size={15} aria-hidden="true" />}
            <span>{isReconciling ? "Reconciling" : "Reconcile"}</span>
          </button>
        </form>

        {latestResult ? (
          <dl className="metric-grid reconciliation-result">
            <div>
              <dt>Status</dt>
              <dd>{latestResult.status}</dd>
            </div>
            <div>
              <dt>Events</dt>
              <dd>{latestResult.updatedEventCount}</dd>
            </div>
            <div>
              <dt>Estimated</dt>
              <dd>${latestResult.estimatedTotalUsd}</dd>
            </div>
            <div>
              <dt>Final</dt>
              <dd>{latestResult.finalTotalUsd ? `$${latestResult.finalTotalUsd}` : "Pending"}</dd>
            </div>
          </dl>
        ) : null}
      </article>

      <article className="panel">
        <div className="panel-header">
          <h2>Recent Reconciliation Runs</h2>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Period</th>
                <th>Estimated</th>
                <th>Final</th>
                <th>Events</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.runId}>
                  <td>{run.status}</td>
                  <td>
                    {formatDate(run.periodStart)} to {formatDate(run.periodEnd)}
                  </td>
                  <td>${run.estimatedTotalUsd}</td>
                  <td>{run.finalTotalUsd ? `$${run.finalTotalUsd}` : "Pending"}</td>
                  <td>{String(run.details.updated_event_count ?? run.details.event_count ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!isLoading && runs.length === 0 ? <p className="empty-text">No reconciliation runs yet.</p> : null}
      </article>
    </section>
  );
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString();
}
