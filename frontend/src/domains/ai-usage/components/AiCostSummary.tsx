import { type AiUsageSummary } from "../../dashboard/types";

type AiCostSummaryProps = {
  usage: AiUsageSummary;
};

export function AiCostSummary({ usage }: AiCostSummaryProps) {
  return (
    <section className="panel ai-panel" aria-labelledby="ai-cost-title">
      <div className="panel-header">
        <h2 id="ai-cost-title">AI Usage</h2>
        <span className="status-badge muted">{usage.status}</span>
      </div>
      <dl className="metric-grid">
        <div>
          <dt>Local model</dt>
          <dd>{usage.localModel}</dd>
        </div>
        <div>
          <dt>Fallback</dt>
          <dd>{usage.fallbackStatus}</dd>
        </div>
        <div>
          <dt>Month-to-date</dt>
          <dd>{usage.estimatedMonthToDate}</dd>
        </div>
        <div>
          <dt>Budget left</dt>
          <dd>{usage.budgetRemaining}</dd>
        </div>
      </dl>
    </section>
  );
}
