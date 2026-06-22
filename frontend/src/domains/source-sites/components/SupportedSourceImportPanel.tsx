import { FileDown, Search } from "lucide-react";
import { FormEvent } from "react";
import { Spinner } from "../../../components/Spinner";
import { type UploadedModel } from "../../models/types";
import { type SiteAdapter } from "../../site-scanning/types";
import { useSupportedSourceImport } from "../hooks/useSupportedSourceImport";
import { formatSourceFileSize } from "../utils/formatSourceFile";

type SupportedSourceImportPanelProps = {
  className?: string;
  heading?: string;
  headingId?: string;
  onImported?: (models: UploadedModel[]) => void;
  showImportedSummary?: boolean;
};

export function SupportedSourceImportPanel({
  className = "panel supported-source-panel",
  heading = "Import From Source",
  headingId = "supported-source-import-title",
  onImported,
  showImportedSummary = false
}: SupportedSourceImportPanelProps) {
  const sourceImport = useSupportedSourceImport({ onImported });

  async function handleDiscoverSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await sourceImport.discover();
  }

  async function handleImportSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await sourceImport.importSelected();
  }

  return (
    <section className={className} aria-labelledby={headingId}>
      <div className="panel-header">
        <div>
          <h2 id={headingId}>{heading}</h2>
          {sourceImport.siteError ? <p className="form-error">{sourceImport.siteError}</p> : null}
        </div>
      </div>
      <SourceSiteDownloadStatus
        activeSite={sourceImport.activeSite}
        isLoading={sourceImport.isLoadingSites}
        siteCount={sourceImport.supportedSites.length}
      />
      <form className="source-project-form" onSubmit={handleDiscoverSubmit}>
        <label className="field-label">
          Source site
          <select
            disabled={sourceImport.supportedSites.length === 0}
            onChange={(event) => sourceImport.updateSelectedSite(event.target.value)}
            required
            value={sourceImport.selectedSiteKey}
          >
            {sourceImport.supportedSites.length === 0 ? <option value="">No configured runners</option> : null}
            {sourceImport.supportedSites.map((site) => (
              <option key={site.siteKey} value={site.siteKey}>
                {site.displayName}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          Project URL
          <input
            disabled={!sourceImport.activeSite}
            onChange={(event) => sourceImport.updateProjectUrl(event.target.value)}
            placeholder={sourceImport.activeSite?.baseUrl ? `${sourceImport.activeSite.baseUrl}model/...` : "Select a source site first"}
            required
            type="url"
            value={sourceImport.projectUrl}
          />
        </label>
        <button
          className="text-button icon-action"
          disabled={!sourceImport.activeSite || !sourceImport.projectUrl.trim() || sourceImport.isDiscovering}
          type="submit"
        >
          {sourceImport.isDiscovering ? <Spinner size={15} /> : <Search size={15} aria-hidden="true" />}
          <span>{sourceImport.isDiscovering ? "Scanning" : "Scan Files"}</span>
        </button>
      </form>
      {sourceImport.sourceError ? <p className="form-error">{sourceImport.sourceError}</p> : null}
      {sourceImport.recentScans.length > 0 ? (
        <div className="source-scan-history" aria-label="Saved source project scans">
          <div className="source-file-list-header">
            <strong>Saved scans</strong>
            <span className="status-badge muted">{sourceImport.recentScans.length} projects</span>
          </div>
          {sourceImport.recentScans.slice(0, 3).map((scan) => (
            <button className="source-scan-row" key={scan.scanId ?? scan.sourceProjectUrl} onClick={() => sourceImport.loadRecentScan(scan)} type="button">
              <span>
                <strong>{scan.projectTitle ?? scan.sourceProjectUrl}</strong>
                <small>{scan.files.length} files saved from {scan.siteKey}</small>
              </span>
              <span className="status-badge muted">Load</span>
            </button>
          ))}
        </div>
      ) : null}
      {sourceImport.sourceFiles ? (
        <form className="source-file-import" onSubmit={handleImportSubmit}>
          <div className="source-file-list" aria-label="Discovered source files">
            <div className="source-file-list-header">
              <strong>{sourceImport.sourceFiles.projectTitle ?? "Source project"}</strong>
              <span className="status-badge muted">{sourceImport.sourceFiles.files.length} files stored</span>
            </div>
            {sourceImport.sourceFiles.files.map((sourceFile) => (
              <label className={sourceFile.supportedModelFile ? "source-file-row" : "source-file-row disabled"} key={sourceFile.fileId}>
                <input
                  checked={sourceImport.selectedFileIds.includes(sourceFile.fileId)}
                  disabled={!sourceFile.supportedModelFile}
                  onChange={() => sourceImport.toggleFile(sourceFile.fileId)}
                  type="checkbox"
                />
                <span>
                  <strong>{sourceFile.filename}</strong>
                  <small>
                    {sourceFile.fileFormat.toUpperCase()} - {formatSourceFileSize(sourceFile.sizeBytes)}
                  </small>
                </span>
                {sourceFile.supportedModelFile ? (
                  <span className="status-badge ok">Importable</span>
                ) : (
                  <span className="status-badge muted">Not importable</span>
                )}
              </label>
            ))}
          </div>
          <label className="field-label">
            Title
            <input
              onChange={(event) => sourceImport.setTitle(event.target.value)}
              placeholder="Optional for one selected file"
              type="text"
              value={sourceImport.title}
            />
          </label>
          <button
            className="primary-action icon-action"
            disabled={sourceImport.selectedFileIds.length === 0 || sourceImport.isImporting}
            type="submit"
          >
            {sourceImport.isImporting ? <Spinner size={15} /> : <FileDown size={15} aria-hidden="true" />}
            <span>{sourceImport.isImporting ? "Downloading" : `Download Selected (${sourceImport.selectedFileIds.length})`}</span>
          </button>
        </form>
      ) : null}
      {showImportedSummary && sourceImport.importedModels.length > 0 ? (
        <div className="source-import-summary" aria-label="Imported source models">
          {sourceImport.importedModels.slice(0, 3).map((model) => (
            <div key={model.id}>
              <strong>{model.title}</strong>
              <span className="status-badge ok">{model.status}</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function SourceSiteDownloadStatus({
  activeSite,
  isLoading,
  siteCount
}: {
  activeSite: SiteAdapter | null;
  isLoading: boolean;
  siteCount: number;
}) {
  if (isLoading) {
    return <p className="muted-copy">Loading configured source runners.</p>;
  }
  if (siteCount === 0) {
    return <p className="muted-copy">No enabled source site runners support managed file downloads yet.</p>;
  }
  return (
    <div className="source-download-status" aria-label="Source download support">
      <div>
        <strong>{activeSite?.displayName ?? "Select a source site"}</strong>
        <span className="status-badge ok">Runner downloads available</span>
      </div>
    </div>
  );
}
