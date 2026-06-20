import { useEffect, useState } from "react";
import { confirmDiscoveredPrinter, deletePrinter, listPrinters, scanPrinters } from "../api/printersApi";
import {
  type DiscoveredPrinter,
  type Printer,
  type PrinterScanResult,
  type PrinterScanSettings
} from "../types";

const defaultScanSettings: PrinterScanSettings = {
  scanMethod: "combined",
  targetCidr: "",
  maxHosts: 254,
  timeoutSeconds: 20,
  connectTimeoutSeconds: 2,
  ports: "80,443,4408,5000,6000,7125,8000,8080,8081,8883"
};

type UsePrintersOptions = {
  enabled?: boolean;
};

export function usePrinters({ enabled = true }: UsePrintersOptions = {}) {
  const [printers, setPrinters] = useState<Printer[]>([]);
  const [scanResult, setScanResult] = useState<PrinterScanResult | null>(null);
  const [scanSettings, setScanSettings] = useState<PrinterScanSettings>(defaultScanSettings);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(enabled);
  const [isScanning, setIsScanning] = useState(false);
  const [addingAction, setAddingAction] = useState<string | null>(null);

  async function refreshPrinters() {
    setIsLoading(true);
    setError(null);
    try {
      setPrinters(await listPrinters());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Printer list failed");
    } finally {
      setIsLoading(false);
    }
  }

  async function runScan() {
    setIsScanning(true);
    setError(null);
    try {
      setScanResult(await scanPrinters(scanSettings));
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "Printer scan failed");
    } finally {
      setIsScanning(false);
    }
  }

  async function addDiscoveredPrinter(printer: DiscoveredPrinter) {
    setAddingAction(discoveredPrinterKey(printer));
    setError(null);
    try {
      const created = await confirmDiscoveredPrinter(printer);
      setPrinters((current) => [...current, created]);
    } catch (addError) {
      setError(addError instanceof Error ? addError.message : "Add discovered printer failed");
    } finally {
      setAddingAction(null);
    }
  }

  async function removePrinter(printerId: number) {
    setError(null);
    try {
      await deletePrinter(printerId);
      setPrinters((current) => current.filter((printer) => printer.id !== printerId));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Delete printer failed");
    }
  }

  useEffect(() => {
    if (!enabled) {
      setPrinters([]);
      setScanResult(null);
      setError(null);
      setIsLoading(false);
      setIsScanning(false);
      setAddingAction(null);
      return;
    }
    void refreshPrinters();
  }, [enabled]);

  return {
    addDiscoveredPrinter,
    addingAction,
    error,
    isAdding: addingAction !== null,
    isLoading,
    isScanning,
    printers,
    refreshPrinters,
    removePrinter,
    runScan,
    scanSettings,
    scanResult,
    setScanSettings
  };
}

export type PrintersState = ReturnType<typeof usePrinters>;

export function discoveredPrinterKey(printer: DiscoveredPrinter) {
  return `${printer.host}:${printer.port}:${printer.serviceType}`;
}
