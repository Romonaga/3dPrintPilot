import { type ResourceSnapshot } from "../../dashboard/types";

type ResourceSummaryProps = {
  resources: ResourceSnapshot;
};

export function ResourceSummary({ resources }: ResourceSummaryProps) {
  return (
    <section className="panel resource-panel" aria-labelledby="resource-title">
      <div className="panel-header">
        <h2 id="resource-title">Hardware</h2>
        <span className="status-badge muted">{resources.status}</span>
      </div>
      <dl className="resource-list">
        <div>
          <dt>GPU</dt>
          <dd>{resources.gpuName}</dd>
        </div>
        <div>
          <dt>VRAM</dt>
          <dd>{resources.vram}</dd>
        </div>
        <div>
          <dt>Queue</dt>
          <dd>{resources.queueDepth}</dd>
        </div>
        <div>
          <dt>CPU</dt>
          <dd>{resources.cpu}</dd>
        </div>
      </dl>
    </section>
  );
}
