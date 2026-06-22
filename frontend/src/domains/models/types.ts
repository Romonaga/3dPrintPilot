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
  payload: ModelFilePayload | null;
  createdAt: string;
};

export type ModelFilePayload = {
  sourceProjectUrl: string;
  sourceFileUrl: string;
  compression: string;
  originalSizeBytes: number;
  compressedSizeBytes: number;
  originalSha256: string;
  compressedSha256: string;
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

export type ImportDownloadedModelInput = {
  file: File;
  title: string;
  sourceProjectUrl: string;
  sourceFileUrl: string;
};

export type SourceModelFile = {
  fileId: string;
  filename: string;
  fileFormat: string;
  sizeBytes: number | null;
  sourceFileUrl: string;
  supportedModelFile: boolean;
  createdAt: string | null;
  notes: string | null;
};

export type SourceProjectFiles = {
  scanId: number | null;
  siteKey: string;
  sourceProjectUrl: string;
  externalProjectId: string;
  projectTitle: string | null;
  scannedAt: string | null;
  files: SourceModelFile[];
};

export type DiscoverSourceFilesInput = {
  siteKey: string;
  sourceProjectUrl: string;
};

export type ImportSourceFilesInput = {
  siteKey: string;
  sourceProjectUrl: string;
  fileIds: string[];
  title: string;
};
