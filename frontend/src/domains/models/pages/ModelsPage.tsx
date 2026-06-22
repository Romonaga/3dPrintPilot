import { Download, RefreshCw, Upload } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { type ModelFile, type UploadedModel } from "../types";
import { useModels } from "../hooks/useModels";
import { listSiteAdapters } from "../../site-scanning/api/siteScanningApi";
import { type SiteAdapter } from "../../site-scanning/types";

export default function ModelsPage() {
  const models = useModels();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importTitle, setImportTitle] = useState("");
  const [sourceProjectUrl, setSourceProjectUrl] = useState("");
  const [sourceFileUrl, setSourceFileUrl] = useState("");
  const [sourceSites, setSourceSites] = useState<SiteAdapter[]>([]);
  const [sourceSiteError, setSourceSiteError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listSiteAdapters()
      .then((sites) => {
        if (active) {
          setSourceSites(sites);
          setSourceSiteError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setSourceSiteError(err instanceof Error ? err.message : "Source site catalog failed");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      return;
    }
    const form = event.currentTarget;
    await models.submitUpload({ file, title, sourceUrl });
    setFile(null);
    setTitle("");
    setSourceUrl("");
    form.reset();
  }

  async function handleImportSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!importFile) {
      return;
    }
    const form = event.currentTarget;
    await models.submitDownloadedImport({
      file: importFile,
      title: importTitle,
      sourceProjectUrl,
      sourceFileUrl
    });
    setImportFile(null);
    setImportTitle("");
    setSourceProjectUrl("");
    setSourceFileUrl("");
    form.reset();
  }

  return (
    <section className="models-page" aria-label="Models">
      <section className="panel model-upload-panel" aria-labelledby="model-upload-title">
        <div className="panel-header">
          <h2 id="model-upload-title">Upload Model</h2>
          <button className="icon-only-button" type="button" onClick={models.refreshModels} aria-label="Refresh models">
            <RefreshCw size={16} aria-hidden="true" />
          </button>
        </div>
        <form className="model-upload-form" onSubmit={handleSubmit}>
          <label className="field-label">
            File
            <input
              accept=".stl,.3mf,model/stl,model/3mf"
              onChange={(event) => setFile(event.currentTarget.files?.[0] ?? null)}
              required
              type="file"
            />
          </label>
          <label className="field-label">
            Title
            <input onChange={(event) => setTitle(event.target.value)} placeholder="Optional" type="text" value={title} />
          </label>
          <label className="field-label">
            Source URL
            <input onChange={(event) => setSourceUrl(event.target.value)} placeholder="Optional" type="url" value={sourceUrl} />
          </label>
          <button className="primary-action icon-action" disabled={!file || models.isUploading} type="submit">
            {models.isUploading ? <Spinner size={15} /> : <Upload size={15} aria-hidden="true" />}
            <span>{models.isUploading ? "Uploading" : "Upload"}</span>
          </button>
        </form>
        {models.error ? <p className="error-text">{models.error}</p> : null}
      </section>

      <section className="panel model-import-panel" aria-labelledby="model-import-title">
        <div className="panel-header">
          <div>
            <h2 id="model-import-title">Import From Source</h2>
            {sourceSiteError ? <p className="form-error">{sourceSiteError}</p> : null}
          </div>
        </div>
        <SourceSiteDownloadStatus sites={sourceSites} />
        <form className="model-upload-form" onSubmit={handleImportSubmit}>
          <label className="field-label">
            Downloaded File
            <input
              accept=".stl,.3mf,model/stl,model/3mf"
              onChange={(event) => setImportFile(event.currentTarget.files?.[0] ?? null)}
              required
              type="file"
            />
          </label>
          <label className="field-label">
            Title
            <input onChange={(event) => setImportTitle(event.target.value)} placeholder="Optional" type="text" value={importTitle} />
          </label>
          <label className="field-label">
            Source Project URL
            <input
              onChange={(event) => setSourceProjectUrl(event.target.value)}
              placeholder="https://www.printables.com/model/..."
              required
              type="url"
              value={sourceProjectUrl}
            />
          </label>
          <label className="field-label">
            Source File URL
            <input
              onChange={(event) => setSourceFileUrl(event.target.value)}
              placeholder="https://..."
              required
              type="url"
              value={sourceFileUrl}
            />
          </label>
          <button
            className="primary-action icon-action"
            disabled={!importFile || !sourceProjectUrl.trim() || !sourceFileUrl.trim() || models.isImporting}
            type="submit"
          >
            {models.isImporting ? <Spinner size={15} /> : <Download size={15} aria-hidden="true" />}
            <span>{models.isImporting ? "Importing" : "Import Downloaded File"}</span>
          </button>
        </form>
      </section>

      <section className="panel model-list-panel" aria-labelledby="model-list-title">
        <div className="panel-header">
          <h2 id="model-list-title">Model Library</h2>
          <span className="status-badge muted">{models.isLoading ? "Loading" : `${models.models.length} models`}</span>
        </div>
        <div className="model-list">
          {models.models.map((model) => (
            <button
              className={model.id === models.selectedModelId ? "model-row active" : "model-row"}
              key={model.id}
              onClick={() => models.setSelectedModelId(model.id)}
              type="button"
            >
              <span>
                <strong>{model.title}</strong>
                <small>{model.files[0]?.filename ?? "No file"}</small>
              </span>
              <span className="status-badge ok">{model.status}</span>
            </button>
          ))}
          {!models.isLoading && models.models.length === 0 ? <p className="empty-text">No models uploaded yet.</p> : null}
        </div>
      </section>

      <ModelDetail model={models.selectedModel} />
    </section>
  );
}

function SourceSiteDownloadStatus({ sites }: { sites: SiteAdapter[] }) {
  const managedSites = sites.filter((site) => site.supportLevel !== "generic_only");
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

function ModelDetail({ model }: { model: UploadedModel | null }) {
  const file = model?.files[0] ?? null;
  const geometry = file?.geometry ?? null;

  return (
    <section className="panel model-detail-panel" aria-labelledby="model-detail-title">
      <div className="panel-header">
        <h2 id="model-detail-title">Geometry</h2>
        {file ? <span className="status-badge muted">Job {file.analysisJobId ?? "pending"}</span> : null}
      </div>
      {!model || !file || !geometry ? (
        <p className="empty-text">Select an uploaded model to inspect geometry.</p>
      ) : (
        <>
          <div className="model-detail-title">
            <h3>{model.title}</h3>
            {model.sourceUrl ? <a href={model.sourceUrl}>{model.sourceUrl}</a> : null}
          </div>
          {file.payload ? (
            <div className="model-source-links">
              <a href={file.payload.sourceProjectUrl}>Source project</a>
              <a href={file.payload.sourceFileUrl}>Source file</a>
              <span>{file.payload.compression.toUpperCase()} stored</span>
            </div>
          ) : null}
          <dl className="metric-grid model-geometry-grid">
            <Metric label="Format" value={file.fileFormat.toUpperCase()} />
            <Metric label="Triangles" value={geometry.triangleCount.toLocaleString()} />
            <Metric label="Size X" value={formatMm(geometry.sizeXmm)} />
            <Metric label="Size Y" value={formatMm(geometry.sizeYmm)} />
            <Metric label="Size Z" value={formatMm(geometry.sizeZmm)} />
            <Metric label="Volume" value={geometry.volumeMm3 === null ? "Unknown" : `${geometry.volumeMm3.toFixed(2)} mm3`} />
          </dl>
          <WarningList file={file} />
        </>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function WarningList({ file }: { file: ModelFile }) {
  const warnings = [...file.analysisWarnings, ...(file.geometry?.warnings ?? [])].filter((warning, index, all) => all.indexOf(warning) === index);
  if (warnings.length === 0) {
    return <p className="empty-text">No parser warnings recorded.</p>;
  }
  return (
    <ul className="model-warning-list">
      {warnings.map((warning) => (
        <li key={warning}>{warning}</li>
      ))}
    </ul>
  );
}

function formatMm(value: number | null) {
  return value === null ? "Unknown" : `${value.toFixed(2)} mm`;
}
