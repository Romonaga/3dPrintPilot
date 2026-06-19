import { apiFetch } from "../../../lib/apiFetch";
import { type ResourceStatus } from "../types";

type ApiResourceStatus = {
  cpu: { cores: number; load_average: number[] | null };
  memory: { total_bytes: number | null; available_bytes: number | null; used_percent: number | null };
  gpu: {
    available: boolean;
    name: string | null;
    utilization_percent: number | null;
    memory_used_mib: number | null;
    memory_total_mib: number | null;
    memory_used_percent: number | null;
    temperature_c: number | null;
    error: string | null;
  };
  queues?: Record<
    string,
    {
      pending_count: number;
      active_count: number;
      max_concurrent: number;
      supported_job_types: string[];
    }
  >;
  ollama?: { available: boolean; base_url: string; model: string; error: string | null } | null;
  local_llm?: {
    max_concurrent_requests: number;
    request_timeout_seconds: number;
    max_context_tokens: number;
    max_output_tokens: number;
    min_free_vram_mib: number;
    max_gpu_memory_used_percent: number;
    max_gpu_temperature_c: number;
    oom_cooldown_seconds: number;
  } | null;
};

export async function getResourceStatus(): Promise<ResourceStatus> {
  const response = await apiFetch("/api/resources/status");
  if (!response.ok) {
    throw new Error(`Resource status failed with HTTP ${response.status}`);
  }
  return fromApi(await response.json());
}

function fromApi(status: ApiResourceStatus): ResourceStatus {
  return {
    cpu: {
      cores: status.cpu.cores,
      loadAverage: status.cpu.load_average
    },
    memory: {
      totalBytes: status.memory.total_bytes,
      availableBytes: status.memory.available_bytes,
      usedPercent: status.memory.used_percent
    },
    gpu: {
      available: status.gpu.available,
      name: status.gpu.name,
      utilizationPercent: status.gpu.utilization_percent,
      memoryUsedMib: status.gpu.memory_used_mib,
      memoryTotalMib: status.gpu.memory_total_mib,
      memoryUsedPercent: status.gpu.memory_used_percent,
      temperatureC: status.gpu.temperature_c,
      error: status.gpu.error
    },
    queues: Object.fromEntries(
      Object.entries(status.queues ?? {}).map(([key, queue]) => [
        key,
        {
          pendingCount: queue.pending_count,
          activeCount: queue.active_count,
          maxConcurrent: queue.max_concurrent,
          supportedJobTypes: queue.supported_job_types
        }
      ])
    ),
    ollama: status.ollama
      ? {
          available: status.ollama.available,
          baseUrl: status.ollama.base_url,
          model: status.ollama.model,
          error: status.ollama.error
        }
      : null,
    localLlm: status.local_llm
      ? {
          maxConcurrentRequests: status.local_llm.max_concurrent_requests,
          requestTimeoutSeconds: status.local_llm.request_timeout_seconds,
          maxContextTokens: status.local_llm.max_context_tokens,
          maxOutputTokens: status.local_llm.max_output_tokens,
          minFreeVramMib: status.local_llm.min_free_vram_mib,
          maxGpuMemoryUsedPercent: status.local_llm.max_gpu_memory_used_percent,
          maxGpuTemperatureC: status.local_llm.max_gpu_temperature_c,
          oomCooldownSeconds: status.local_llm.oom_cooldown_seconds
        }
      : null
  };
}
