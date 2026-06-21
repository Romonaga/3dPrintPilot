import { Pause, Play, RefreshCw, Square, Upload } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import {
  cancelPrinterPrint,
  getPrinterJobStatus,
  listPrinterFiles,
  pausePrinterPrint,
  resumePrinterPrint,
  startPrinterFile,
  uploadPrinterFile
} from "../api/printersApi";
import { type Printer, type PrinterFile, type PrinterJobStatus } from "../types";

type PrinterControlPanelProps = {
  printer: Printer;
};

type PendingAction = "refresh" | "upload" | "start" | "pause" | "resume" | "cancel" | null;

export function PrinterControlPanel({ printer }: PrinterControlPanelProps) {
  const supported = useMemo(() => supportsMoonrakerControl(printer), [printer]);
  const [files, setFiles] = useState<PrinterFile[]>([]);
  const [jobStatus, setJobStatus] = useState<PrinterJobStatus | null>(null);
  const [selectedPath, setSelectedPath] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const refreshControlData = useCallback(async () => {
    if (!supported) {
      return;
    }
    setPendingAction((current) => current ?? "refresh");
    setError(null);
    try {
      const [nextStatus, nextFiles] = await Promise.all([getPrinterJobStatus(printer.id), listPrinterFiles(printer.id)]);
      setJobStatus(nextStatus);
      setFiles(nextFiles);
      setSelectedPath((current) => {
        if (current && nextFiles.some((file) => file.path === current)) {
          return current;
        }
        return nextFiles[0]?.path || "";
      });
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Printer control refresh failed");
    } finally {
      setPendingAction((current) => (current === "refresh" ? null : current));
    }
  }, [printer.id, supported]);

  useEffect(() => {
    setFiles([]);
    setJobStatus(null);
    setSelectedPath("");
    setUploadFile(null);
    setFileInputKey((current) => current + 1);
    setError(null);
    setStatusMessage(null);
    void refreshControlData();
  }, [refreshControlData]);

  if (!supported) {
    return null;
  }

  const progressPercent = formatProgressPercent(jobStatus?.progress);
  const selectedFileReady = selectedPath.trim().length > 0;
  const actionInFlight = pendingAction !== null;

  async function handleUpload() {
    if (!uploadFile) {
      return;
    }
    if (!isSlicedPrintFile(uploadFile.name)) {
      setError("Only already-sliced .gcode or .gcode.gz files are supported");
      return;
    }
    setPendingAction("upload");
    setError(null);
    setStatusMessage(null);
    try {
      await uploadPrinterFile(printer.id, uploadFile);
      setStatusMessage(`Uploaded ${uploadFile.name}`);
      setUploadFile(null);
      setFileInputKey((current) => current + 1);
      await refreshControlData();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Printer file upload failed");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleStart() {
    if (!selectedFileReady) {
      return;
    }
    if (!window.confirm(`Start print file "${selectedPath}" on ${printer.name}?`)) {
      return;
    }
    setPendingAction("start");
    setError(null);
    setStatusMessage(null);
    try {
      await startPrinterFile(printer.id, selectedPath);
      setStatusMessage(`Started ${selectedPath}`);
      await refreshControlData();
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Printer start failed");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleJobAction(action: "pause" | "resume" | "cancel") {
    if (action === "cancel" && !window.confirm(`Cancel the current print on ${printer.name}?`)) {
      return;
    }
    setPendingAction(action);
    setError(null);
    setStatusMessage(null);
    try {
      if (action === "pause") {
        await pausePrinterPrint(printer.id);
      } else if (action === "resume") {
        await resumePrinterPrint(printer.id);
      } else {
        await cancelPrinterPrint(printer.id);
      }
      setStatusMessage(`${labelAction(action)} accepted`);
      await refreshControlData();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : `Printer ${action} failed`);
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="printer-control-panel" aria-label={`Controls for ${printer.name}`} role="group">
      <div className="printer-control-header">
        <div>
          <h4>Moonraker Controls</h4>
          <p>{jobStatus ? formatJobSummary(jobStatus) : "Status not loaded"}</p>
        </div>
        <button
          aria-label={`Refresh controls for ${printer.name}`}
          className="icon-only-button"
          disabled={actionInFlight}
          onClick={() => void refreshControlData()}
          title="Refresh controls"
          type="button"
        >
          {pendingAction === "refresh" ? <Spinner size={14} /> : <RefreshCw size={15} aria-hidden="true" />}
        </button>
      </div>

      <div className="printer-progress-row">
        <progress aria-label={`Print progress for ${printer.name}`} max={100} value={progressPercent ?? 0} />
        <span>{progressPercent === null ? "Progress unknown" : `${progressPercent}%`}</span>
      </div>

      <div className="printer-file-grid">
        <label className="field-label">
          <span>Sliced file</span>
          <select value={selectedPath} onChange={(event) => setSelectedPath(event.target.value)}>
            {files.length === 0 ? <option value="">No sliced files found</option> : null}
            {files.map((file) => (
              <option value={file.path} key={file.path}>
                {file.path}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary-action icon-action"
          disabled={actionInFlight || !selectedFileReady}
          onClick={() => void handleStart()}
          type="button"
        >
          {pendingAction === "start" ? <Spinner size={14} /> : <Play size={15} aria-hidden="true" />}
          <span>Start</span>
        </button>
      </div>

      <div className="printer-upload-row">
        <label className="field-label">
          <span>Upload sliced file</span>
          <input
            accept=".gcode,.gcode.gz"
            key={fileInputKey}
            onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
        <button
          className="text-button icon-action"
          disabled={actionInFlight || uploadFile === null}
          onClick={() => void handleUpload()}
          type="button"
        >
          {pendingAction === "upload" ? <Spinner size={14} /> : <Upload size={15} aria-hidden="true" />}
          <span>Upload</span>
        </button>
      </div>

      <div className="printer-job-actions" aria-label={`Print actions for ${printer.name}`}>
        <button
          className="text-button icon-action"
          disabled={actionInFlight}
          onClick={() => void handleJobAction("pause")}
          type="button"
        >
          {pendingAction === "pause" ? <Spinner size={14} /> : <Pause size={15} aria-hidden="true" />}
          <span>Pause</span>
        </button>
        <button
          className="text-button icon-action"
          disabled={actionInFlight}
          onClick={() => void handleJobAction("resume")}
          type="button"
        >
          {pendingAction === "resume" ? <Spinner size={14} /> : <Play size={15} aria-hidden="true" />}
          <span>Resume</span>
        </button>
        <button
          className="text-button icon-action danger-action"
          disabled={actionInFlight}
          onClick={() => void handleJobAction("cancel")}
          type="button"
        >
          {pendingAction === "cancel" ? <Spinner size={14} /> : <Square size={15} aria-hidden="true" />}
          <span>Cancel</span>
        </button>
      </div>

      {files.length > 0 ? (
        <div className="printer-file-list" aria-label={`Files on ${printer.name}`}>
          {files.slice(0, 5).map((file) => (
            <button
              className={file.path === selectedPath ? "printer-file-row active" : "printer-file-row"}
              key={file.path}
              onClick={() => setSelectedPath(file.path)}
              type="button"
            >
              <span>{file.path}</span>
              <small>{formatFileDetails(file)}</small>
            </button>
          ))}
        </div>
      ) : null}

      {statusMessage ? <p className="success-text">{statusMessage}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
    </div>
  );
}

export function supportsMoonrakerControl(printer: Printer) {
  const capabilities = printer.capabilities ?? {};
  const capabilityAdapter = typeof capabilities.adapter === "string" ? capabilities.adapter : "";
  const haystack = `${printer.adapterType ?? ""} ${printer.printerType} ${capabilityAdapter}`.toLowerCase();
  return ["moonraker", "klipper", "snapmaker", "creality"].some((marker) => haystack.includes(marker));
}

function isSlicedPrintFile(filename: string) {
  const lowerFilename = filename.toLowerCase();
  return lowerFilename.endsWith(".gcode") || lowerFilename.endsWith(".gcode.gz");
}

function formatProgressPercent(progress: number | null | undefined) {
  if (typeof progress !== "number" || !Number.isFinite(progress)) {
    return null;
  }
  const normalized = progress <= 1 ? progress * 100 : progress;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function formatJobSummary(status: PrinterJobStatus) {
  const filename = status.filename ? ` - ${status.filename}` : "";
  return `${status.state}${filename}`;
}

function formatFileDetails(file: PrinterFile) {
  const size = file.size === null ? "size unknown" : formatBytes(file.size);
  const modified = file.modified === null ? "modified unknown" : new Date(file.modified * 1000).toLocaleString();
  return `${size} / ${modified}`;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const kib = bytes / 1024;
  if (kib < 1024) {
    return `${kib.toFixed(1)} KiB`;
  }
  return `${(kib / 1024).toFixed(1)} MiB`;
}

function labelAction(action: "pause" | "resume" | "cancel") {
  return action.charAt(0).toUpperCase() + action.slice(1);
}
