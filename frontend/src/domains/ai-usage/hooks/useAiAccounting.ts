import { useCallback, useEffect, useState } from "react";
import { getAiAccountingStatus, listReconciliationRuns, reconcileOpenAiCosts } from "../api/aiUsageApi";
import { type AiAccountingStatus, type CostReconciliationResult, type CostReconciliationRun } from "../types";

export function useAiAccounting() {
  const [status, setStatus] = useState<AiAccountingStatus | null>(null);
  const [runs, setRuns] = useState<CostReconciliationRun[]>([]);
  const [latestResult, setLatestResult] = useState<CostReconciliationResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isReconciling, setIsReconciling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [nextStatus, nextRuns] = await Promise.all([getAiAccountingStatus(), listReconciliationRuns()]);
      setStatus(nextStatus);
      setRuns(nextRuns);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI accounting load failed");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function reconcile(periodStart: string, periodEnd: string) {
    setIsReconciling(true);
    setError(null);
    setLatestResult(null);
    try {
      const result = await reconcileOpenAiCosts(periodStart, periodEnd);
      setLatestResult(result);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "OpenAI reconciliation failed");
    } finally {
      setIsReconciling(false);
    }
  }

  return { status, runs, latestResult, isLoading, isReconciling, error, reload, reconcile };
}
