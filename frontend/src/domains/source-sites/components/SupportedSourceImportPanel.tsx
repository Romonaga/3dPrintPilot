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
        isLoading={sourceImport.isLoadingSites}
        managedSites={sourceImport.managedSites}
      />
      <form className="source-project-form" onSubmit={handleDiscoverSubmit}>
        <label className="field-label">
          Printables Project URL
          <input
            onChange={(event) => sourceImport.updateProjectUrl(event.target.value)}
            placeholder="https://www.printables.com/model/..."
            required
            type="url"
            value={sourceImport.projectUrl}
          />
        </label>
        <button className="text-button icon-action" disabled={!sourceImport.projectUrl.trim() || sourceImport.isDiscovering} type="submit">
          {sourceImport.isDiscovering ? <Spinner size={15} /> : <Search size={15} aria-hidden="true" />}
          <span>{sourceImport.isDiscovering ? "Discovering" : "Discover Files"}</span>
        </button>
      </form>
      {sourceImport.sourceError ? <p className="form-error">{sourceImport.sourceError}</p> : null}
      {sourceImport.sourceFiles ? (
        <form className="source-file-import" onSubmit={handleImportSubmit}>
          <div className="source-file-list" aria-label="Discovered source files">
            <div className="source-file-list-header">
              <strong>{sourceImport.sourceFiles.projectTitle ?? "Printables project"}</strong>
              <span className="status-badge muted">{sourceImport.sourceFiles.files.length} files</span>
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
            <span>{sourceImport.isImporting ? "Importing" : `Import Selected (${sourceImport.selectedFileIds.length})`}</span>
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
  isLoading,
  managedSites
}: {
  isLoading: boolean;
  managedSites: SiteAdapter[];
}) {
  if (isLoading) {
    return <p className="muted-copy">Loading supported sites.</p>;
  }
  if (managedSites.length === 0) {
    return <p className="muted-copy">Unsupported sites can still be tracked with project and file links after manual download.</p>;
  }
  return (
    <div className="source-download-status" aria-label="Source download support">
      {managedSites.map((site) => (
        <div key={site.siteKey}>
          <strong>{site.displayName}</strong>
          <span className={site.supportsDownloads ? "status-badge ok" : "status-badge muted"}>
            {site.supportsDownloads ? "Managed downloads available" : "Manual download required"}
          </span>
        </div>
      ))}
    </div>
  );
}
