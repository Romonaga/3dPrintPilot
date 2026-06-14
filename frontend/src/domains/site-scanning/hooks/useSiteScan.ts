import { useState } from "react";
import { createSiteScan } from "../api/siteScanningApi";
import { type SiteScanLimits, type SiteScanResult } from "../types";

const defaultLimits: SiteScanLimits = {
  maxDepth: 1,
  maxPages: 5,
  maxRuntimeSeconds: 300,
  sameDomainOnly: true,
  perHostConcurrency: 1
};

export function useSiteScan() {
  const [url, setUrl] = useState("https://www.printables.com/");
  const [limits, setLimits] = useState<SiteScanLimits>(defaultLimits);
  const [result, setResult] = useState<SiteScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);

  async function runScan() {
    setIsScanning(true);
    setError(null);
    try {
      setResult(await createSiteScan(url, limits));
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "Scan failed");
    } finally {
      setIsScanning(false);
    }
  }

  return {
    error,
    isScanning,
    limits,
    result,
    runScan,
    setLimits,
    setUrl,
    url
  };
}
