import { apiFetch } from "../../../lib/apiFetch";
import {
  type DiscoverSourceFilesInput,
  type ImportDownloadedModelInput,
  type ImportSourceFilesInput,
  type SourceProjectFiles,
  type UploadedModel,
  type UploadModelInput
} from "../types";

type ApiModelGeometry = {
  units: string;
  size_x_mm: number | null;
  size_y_mm: number | null;
  size_z_mm: number | null;
  volume_mm3: number | null;
  triangle_count: number;
  warnings: string[];
};

type ApiModelFile = {
  id: number;
  filename: string;
  content_type: string | null;
  file_format: string;
  size_bytes: number;
  storage_status: string;
  analysis_status: string;
  analysis_job_id: number | null;
  analysis_warnings: string[];
  geometry: ApiModelGeometry | null;
  payload: ApiModelFilePayload | null;
  created_at: string;
};

type ApiModelFilePayload = {
  source_project_url: string;
  source_file_url: string;
  compression: string;
  original_size_bytes: number;
  compressed_size_bytes: number;
  original_sha256: string;
  compressed_sha256: string;
  created_at: string;
};

type ApiModel = {
  id: number;
  title: string;
  source_url: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  files: ApiModelFile[];
};

type ApiSourceModelFile = {
  file_id: string;
  filename: string;
  file_format: string;
  size_bytes: number | null;
  source_file_url: string;
  supported_model_file: boolean;
  created_at: string | null;
  notes: string | null;
};

type ApiSourceProjectFiles = {
  site_key: string;
  source_project_url: string;
  external_project_id: string;
  project_title: string | null;
  files: ApiSourceModelFile[];
};

export async function listModels(): Promise<UploadedModel[]> {
  const response = await apiFetch("/api/models");
  if (!response.ok) {
    throw new Error(`Model list failed with HTTP ${response.status}`);
  }
  const models = (await response.json()) as ApiModel[];
  return models.map(fromApiModel);
}

export async function uploadModel(input: UploadModelInput): Promise<UploadedModel> {
  const form = new FormData();
  form.append("file", input.file);
  if (input.title.trim()) {
    form.append("title", input.title.trim());
  }
  if (input.sourceUrl.trim()) {
    form.append("source_url", input.sourceUrl.trim());
  }
  const response = await apiFetch("/api/models/uploads", {
    method: "POST",
    body: form
  });
  if (!response.ok) {
    let detail = `Model upload failed with HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Keep HTTP status fallback.
    }
    throw new Error(detail);
  }
  return fromApiModel(await response.json());
}

export async function discoverSourceModelFiles(input: DiscoverSourceFilesInput): Promise<SourceProjectFiles> {
  const response = await apiFetch("/api/models/imports/source-files/discover", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      site_key: input.siteKey,
      source_project_url: input.sourceProjectUrl.trim()
    })
  });
  if (!response.ok) {
    throw new Error(await apiErrorDetail(response, `Source file discovery failed with HTTP ${response.status}`));
  }
  return fromApiSourceProjectFiles(await response.json());
}

export async function importSourceModelFiles(input: ImportSourceFilesInput): Promise<UploadedModel[]> {
  const response = await apiFetch("/api/models/imports/source-files", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      site_key: input.siteKey,
      source_project_url: input.sourceProjectUrl.trim(),
      file_ids: input.fileIds,
      title: input.title.trim() || null
    })
  });
  if (!response.ok) {
    throw new Error(await apiErrorDetail(response, `Source file import failed with HTTP ${response.status}`));
  }
  const models = (await response.json()) as ApiModel[];
  return models.map(fromApiModel);
}

export async function importDownloadedModelFile(input: ImportDownloadedModelInput): Promise<UploadedModel> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("source_project_url", input.sourceProjectUrl.trim());
  form.append("source_file_url", input.sourceFileUrl.trim());
  if (input.title.trim()) {
    form.append("title", input.title.trim());
  }
  const response = await apiFetch("/api/models/imports/downloaded-file", {
    method: "POST",
    body: form
  });
  if (!response.ok) {
    let detail = `Downloaded model import failed with HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Keep HTTP status fallback.
    }
    throw new Error(detail);
  }
  return fromApiModel(await response.json());
}

async function apiErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Keep HTTP status fallback.
  }
  return fallback;
}

function fromApiModel(model: ApiModel): UploadedModel {
  return {
    id: model.id,
    title: model.title,
    sourceUrl: model.source_url,
    status: model.status,
    createdAt: model.created_at,
    updatedAt: model.updated_at,
    files: model.files.map((file) => ({
      id: file.id,
      filename: file.filename,
      contentType: file.content_type,
      fileFormat: file.file_format,
      sizeBytes: file.size_bytes,
      storageStatus: file.storage_status,
      analysisStatus: file.analysis_status,
      analysisJobId: file.analysis_job_id,
      analysisWarnings: file.analysis_warnings,
      geometry: file.geometry
        ? {
            units: file.geometry.units,
            sizeXmm: file.geometry.size_x_mm,
            sizeYmm: file.geometry.size_y_mm,
            sizeZmm: file.geometry.size_z_mm,
            volumeMm3: file.geometry.volume_mm3,
            triangleCount: file.geometry.triangle_count,
            warnings: file.geometry.warnings
          }
        : null,
      payload: file.payload
        ? {
            sourceProjectUrl: file.payload.source_project_url,
            sourceFileUrl: file.payload.source_file_url,
            compression: file.payload.compression,
            originalSizeBytes: file.payload.original_size_bytes,
            compressedSizeBytes: file.payload.compressed_size_bytes,
            originalSha256: file.payload.original_sha256,
            compressedSha256: file.payload.compressed_sha256,
            createdAt: file.payload.created_at
          }
        : null,
      createdAt: file.created_at
    }))
  };
}

function fromApiSourceProjectFiles(project: ApiSourceProjectFiles): SourceProjectFiles {
  return {
    siteKey: project.site_key,
    sourceProjectUrl: project.source_project_url,
    externalProjectId: project.external_project_id,
    projectTitle: project.project_title,
    files: project.files.map((file) => ({
      fileId: file.file_id,
      filename: file.filename,
      fileFormat: file.file_format,
      sizeBytes: file.size_bytes,
      sourceFileUrl: file.source_file_url,
      supportedModelFile: file.supported_model_file,
      createdAt: file.created_at,
      notes: file.notes
    }))
  };
}
