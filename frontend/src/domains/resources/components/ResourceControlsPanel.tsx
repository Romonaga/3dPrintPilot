import { RefreshCw } from "lucide-react";
import { Spinner } from "../../../components/Spinner";
import { StatusBadge } from "../../../components/StatusBadge";
import { useResourceStatus } from "../hooks/useResourceStatus";

export function ResourceControlsPanel() {
  const { status, isLoading, error, reload } = useResourceStatus();
  const queue = status?.queues.local_llm;

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <h2>Resource Controls</h2>
          {error ? <p className="form-error">{error}</p> : null}
        </div>
        <button className="text-button icon-action" type="button" onClick={reload} disabled={isLoading}>
          {isLoading ? <Spinner size={15} /> : <RefreshCw size={15} aria-hidden="true" />}
          <span>Refresh</span>
        </button>
      </div>

      <dl className="resource-list">
        <div>
          <dt>Ollama</dt>
          <dd>
            <StatusBadge
              icon={RefreshCw}
              label={status?.ollama?.available ? "Available" : "Unavailable"}
              tone={status?.ollama?.available ? "ok" : "warn"}
            />
          </dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{status?.ollama?.model ?? "Local model"}</dd>
        </div>
        <div>
          <dt>LLM Queue</dt>
          <dd>
            {queue?.activeCount ?? 0}/{queue?.maxConcurrent ?? 1} active, {queue?.pendingCount ?? 0} queued
          </dd>
        </div>
        <div>
          <dt>Context</dt>
          <dd>{status?.localLlm?.maxContextTokens ?? 8192} tokens</dd>
        </div>
        <div>
          <dt>Output</dt>
          <dd>{status?.localLlm?.maxOutputTokens ?? 2048} tokens</dd>
        </div>
        <div>
          <dt>VRAM Guard</dt>
          <dd>{status?.localLlm?.maxGpuMemoryUsedPercent ?? 88}% used max</dd>
        </div>
        <div>
          <dt>Temperature</dt>
          <dd>{status?.localLlm?.maxGpuTemperatureC ?? 82}C max</dd>
        </div>
        <div>
          <dt>Cooldown</dt>
          <dd>{status?.localLlm?.oomCooldownSeconds ?? 300}s</dd>
        </div>
      </dl>
    </article>
  );
}
