import { apiFetch } from "../../lib/apiFetch";

export async function downloadOperationsBackup() {
  const response = await apiFetch("/api/operations/backup.json");
  if (!response.ok) {
    throw new Error(`Backup export failed with HTTP ${response.status}`);
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "3dprintpilot-backup.json";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}
