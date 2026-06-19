import { type ResourceSnapshot } from "../../dashboard/types";
import { useResourceStatus } from "../hooks/useResourceStatus";

type ResourceSummaryProps = {
  resources: ResourceSnapshot;
};

export function ResourceSummary({ resources }: ResourceSummaryProps) {
  const { status } = useResourceStatus();
  const queue = status?.queues.local_llm;
  const gpuName = status?.gpu.available ? status.gpu.name ?? resources.gpuName : "Unavailable";
  const vram = status?.gpu.memoryUsedPercent !== undefined && status?.gpu.memoryUsedPercent !== null
    ? `${status.gpu.memoryUsedPercent}%`
    : resources.vram;
  const cpu = status?.cpu ? `${status.cpu.cores} threads` : resources.cpu;

  return (
    <section className="panel resource-panel" aria-labelledby="resource-title">
      <div className="panel-header">
        <h2 id="resource-title">Hardware</h2>
        <span className="status-badge warn">GPU Queue</span>
      </div>
      <dl className="resource-list">
        <div>
          <dt>GPU</dt>
          <dd>{gpuName}</dd>
        </div>
        <div>
          <dt>VRAM</dt>
          <dd>{resources.vram}</dd>
        </div>
        <div>
          <dt>Queue</dt>
          <dd>{queue?.pendingCount ?? resources.queueDepth}</dd>
        </div>
        <div>
          <dt>CPU</dt>
          <dd>{cpu}</dd>
        </div>
      </dl>
    </section>
  );
}
