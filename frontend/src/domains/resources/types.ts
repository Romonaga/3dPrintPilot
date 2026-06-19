export type ResourceStatus = {
  cpu: {
    cores: number;
    loadAverage: number[] | null;
  };
  memory: {
    totalBytes: number | null;
    availableBytes: number | null;
    usedPercent: number | null;
  };
  gpu: {
    available: boolean;
    name: string | null;
    utilizationPercent: number | null;
    memoryUsedMib: number | null;
    memoryTotalMib: number | null;
    memoryUsedPercent: number | null;
    temperatureC: number | null;
    error: string | null;
  };
  queues: Record<
    string,
    {
      pendingCount: number;
      activeCount: number;
      maxConcurrent: number;
      supportedJobTypes: string[];
    }
  >;
  ollama: {
    available: boolean;
    baseUrl: string;
    model: string;
    error: string | null;
  } | null;
  localLlm: {
    maxConcurrentRequests: number;
    requestTimeoutSeconds: number;
    maxContextTokens: number;
    maxOutputTokens: number;
    minFreeVramMib: number;
    maxGpuMemoryUsedPercent: number;
    maxGpuTemperatureC: number;
    oomCooldownSeconds: number;
  } | null;
};
