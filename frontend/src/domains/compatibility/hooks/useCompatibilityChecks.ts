import { useCallback, useEffect, useState } from "react";
import { listCompatibilityChecks, runCompatibilityChecks } from "../api/compatibilityApi";
import { type CompatibilityCheckResult, type CompatibilityRunResult } from "../types";

export function useCompatibilityChecks() {
  const [checks, setChecks] = useState<CompatibilityCheckResult[]>([]);
  const [lastRun, setLastRun] = useState<CompatibilityRunResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setChecks(await listCompatibilityChecks());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Compatibility list failed");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function run(scanRunId: number, maxCandidates: number) {
    setIsRunning(true);
    setError(null);
    try {
      const result = await runCompatibilityChecks(scanRunId, maxCandidates);
      setLastRun(result);
      setChecks(result.checks);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Compatibility run failed");
    } finally {
      setIsRunning(false);
    }
  }

  return { checks, lastRun, isLoading, isRunning, error, reload, run };
}
