export type ModelGeometry = {
  units: string;
  sizeXmm: number | null;
  sizeYmm: number | null;
  sizeZmm: number | null;
  volumeMm3: number | null;
  triangleCount: number;
  warnings: string[];
};

export type ModelFile = {
  id: number;
  filename: string;
  contentType: string | null;
  fileFormat: string;
  sizeBytes: number;
  storageStatus: string;
  analysisStatus: string;
  analysisJobId: number | null;
  analysisWarnings: string[];
  geometry: ModelGeometry | null;
  createdAt: string;
};

export type UploadedModel = {
  id: number;
  title: string;
  sourceUrl: string | null;
  status: string;
  createdAt: string;
  updatedAt: string;
  files: ModelFile[];
};

export type UploadModelInput = {
  file: File;
  title: string;
  sourceUrl: string;
};
