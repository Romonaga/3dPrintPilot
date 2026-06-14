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
          <dt>Ollama</dt>
          <dd>{usage.ollamaRequests}</dd>
        </div>
        <div>
          <dt>OpenAI</dt>
          <dd>{usage.openAiFallbacks}</dd>
        </div>
        <div>
          <dt>Estimated</dt>
          <dd>{usage.estimatedCost}</dd>
        </div>
        <div>
          <dt>Final</dt>
          <dd>{usage.finalCost}</dd>
        </div>
      </dl>
    </section>
  );
}

