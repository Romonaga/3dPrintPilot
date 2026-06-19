import { useCallback, useEffect, useState } from "react";
import { getResourceStatus } from "../api/resourcesApi";
import { type ResourceStatus } from "../types";

export function useResourceStatus() {
  const [status, setStatus] = useState<ResourceStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setStatus(await getResourceStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resource status failed");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { status, isLoading, error, reload };
}
