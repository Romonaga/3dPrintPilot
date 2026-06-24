import { useEffect, useState } from "react";
import {
  confirmDiscoveredPrinter,
  deletePrinter,
  getPrinterCapabilityDiagnostics,
  getPrinterJobStatus,
  getPrinterStatus,
  listPrinters,
  scanPrinters
} from "../api/printersApi";
import {
  type DiscoveredPrinter,
  type Printer,
  type PrinterCapabilityDiagnostics,
  type PrinterJobStatus,
  type PrinterScanResult,
  type PrinterScanSettings,
  type PrinterStatus
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

export type PrinterRefreshInfo = {
  status: PrinterStatus;
  jobStatus: PrinterJobStatus | null;
  capabilityDiagnostics: PrinterCapabilityDiagnostics | null;
  refreshedAt: string;
};

export function usePrinters({ enabled = true }: UsePrintersOptions = {}) {
  const [printers, setPrinters] = useState<Printer[]>([]);
  const [printerRefreshInfo, setPrinterRefreshInfo] = useState<Record<number, PrinterRefreshInfo>>({});
  const [printerRefreshErrors, setPrinterRefreshErrors] = useState<Record<number, string>>({});
  const [refreshingPrinterIds, setRefreshingPrinterIds] = useState<Set<number>>(() => new Set());
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

  async function refreshPrinterInfo(printerId: number) {
    const printer = printers.find((item) => item.id === printerId);
    if (!printer) {
      return;
    }
    setRefreshingPrinterIds((current) => new Set(current).add(printerId));
    setPrinterRefreshErrors((current) => removeRecordKey(current, printerId));
    try {
      const status = await getPrinterStatus(printerId);
      const refreshedAt = new Date().toISOString();
      const supportsMoonraker = supportsMoonrakerRefresh(printer, status);
      const [jobResult, diagnosticsResult] = supportsMoonraker
        ? await Promise.allSettled([getPrinterJobStatus(printerId), getPrinterCapabilityDiagnostics(printerId)])
        : [null, null];
      const jobStatus = jobResult && jobResult.status === "fulfilled" ? jobResult.value : null;
      const capabilityDiagnostics = diagnosticsResult && diagnosticsResult.status === "fulfilled" ? diagnosticsResult.value : null;

      setPrinters((current) =>
        current.map((item) =>
          item.id === printerId
            ? {
                ...item,
                state: status.state,
                adapterType: status.adapterType,
                capabilities: { ...item.capabilities, ...status.capabilities },
                lastStatus: status.rawStatus,
                lastStatusAt: status.observedAt
              }
            : item
        )
      );
      setPrinterRefreshInfo((current) => ({
        ...current,
        [printerId]: { status, jobStatus, capabilityDiagnostics, refreshedAt }
      }));

      const partialErrors = [
        jobResult && jobResult.status === "rejected" ? "job telemetry" : null,
        diagnosticsResult && diagnosticsResult.status === "rejected" ? "capability diagnostics" : null
      ].filter((item): item is string => item !== null);
      if (partialErrors.length > 0) {
        setPrinterRefreshErrors((current) => ({
          ...current,
          [printerId]: `Refreshed status; ${partialErrors.join(" and ")} unavailable`
        }));
      }
    } catch (refreshError) {
      setPrinterRefreshErrors((current) => ({
        ...current,
        [printerId]: refreshError instanceof Error ? refreshError.message : "Printer refresh failed"
      }));
    } finally {
      setRefreshingPrinterIds((current) => {
        const next = new Set(current);
        next.delete(printerId);
        return next;
      });
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
      setPrinterRefreshInfo({});
      setPrinterRefreshErrors({});
      setRefreshingPrinterIds(new Set());
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
    printerRefreshErrors,
    printerRefreshInfo,
    printers,
    refreshPrinterInfo,
    refreshPrinters,
    refreshingPrinterIds,
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

function supportsMoonrakerRefresh(printer: Printer, status: PrinterStatus) {
  const printerCapabilityAdapter = typeof printer.capabilities.adapter === "string" ? printer.capabilities.adapter : "";
  const statusCapabilityAdapter = typeof status.capabilities.adapter === "string" ? status.capabilities.adapter : "";
  const haystack = `${printer.adapterType ?? ""} ${printer.printerType} ${status.adapterType} ${printerCapabilityAdapter} ${statusCapabilityAdapter}`.toLowerCase();
  return ["moonraker", "klipper", "snapmaker", "creality"].some((marker) => haystack.includes(marker));
}

function removeRecordKey<T>(record: Record<number, T>, key: number) {
  const { [key]: _removed, ...rest } = record;
  return rest;
}
