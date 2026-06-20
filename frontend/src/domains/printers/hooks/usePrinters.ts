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
      const confirmed = await confirmDiscoveredPrinter(printer);
      setPrinters((current) => upsertPrinter(current, confirmed));
      setScanResult((current) => (current === null ? current : markScanResultKnown(current, confirmed)));
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
  return printer.identityKey ?? `${printer.host}:${printer.port}:${printer.serviceType}`;
}

function upsertPrinter(printers: Printer[], confirmed: Printer) {
  const existingIndex = printers.findIndex((printer) => printer.id === confirmed.id);
  if (existingIndex === -1) {
    return [...printers, confirmed];
  }
  return printers.map((printer) => (printer.id === confirmed.id ? confirmed : printer));
}

function markScanResultKnown(scanResult: PrinterScanResult, confirmed: Printer): PrinterScanResult {
  const printers = scanResult.printers.map((printer) => markDiscoveryKnown(printer, confirmed));
  const groups = scanResult.groups.map((group) => {
    const endpoints = group.endpoints.map((endpoint) => markDiscoveryKnown(endpoint, confirmed));
    const matchedPrinterId =
      group.matchedPrinterId ??
      endpoints.find((endpoint) => endpoint.matchedPrinterId === confirmed.id)?.matchedPrinterId ??
      null;
    return { ...group, matchedPrinterId, endpoints };
  });
  return { ...scanResult, printers, groups };
}

function markDiscoveryKnown(discovered: DiscoveredPrinter, confirmed: Printer): DiscoveredPrinter {
  if (!discoveryMatchesPrinter(discovered, confirmed)) {
    return discovered;
  }
  return {
    ...discovered,
    matchedPrinterId: confirmed.id,
    identityKey: discovered.identityKey ?? confirmed.identityKey
  };
}

function discoveryMatchesPrinter(discovered: DiscoveredPrinter, confirmed: Printer) {
  if (discovered.matchedPrinterId === confirmed.id) {
    return true;
  }
  if (discovered.identityKey && confirmed.identityKey && discovered.identityKey === confirmed.identityKey) {
    return true;
  }
  return (
    discovered.host === confirmed.host &&
    discovered.port === confirmed.port &&
    discovered.protocol === confirmed.protocol
  );
}
