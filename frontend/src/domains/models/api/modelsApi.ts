import { apiFetch } from "../../../lib/apiFetch";
import { type UploadedModel, type UploadModelInput } from "../types";

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
      createdAt: file.created_at
    }))
  };
}
