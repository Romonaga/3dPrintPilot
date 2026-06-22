import { useEffect, useState } from "react";
import { importDownloadedModelFile, listModels, uploadModel } from "../api/modelsApi";
import { type ImportDownloadedModelInput, type UploadedModel, type UploadModelInput } from "../types";

export function useModels() {
  const [models, setModels] = useState<UploadedModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  async function refreshModels() {
    setIsLoading(true);
    setError(null);
    try {
      const loaded = await listModels();
      setModels(loaded);
      setSelectedModelId((current) => current ?? loaded[0]?.id ?? null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Model list failed");
    } finally {
      setIsLoading(false);
    }
  }

  async function submitUpload(input: UploadModelInput) {
    setIsUploading(true);
    setError(null);
    try {
      const created = await uploadModel(input);
      setModels((current) => [created, ...current]);
      setSelectedModelId(created.id);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Model upload failed");
    } finally {
      setIsUploading(false);
    }
  }

  async function submitDownloadedImport(input: ImportDownloadedModelInput) {
    setIsImporting(true);
    setError(null);
    try {
      const created = await importDownloadedModelFile(input);
      setModels((current) => [created, ...current]);
      setSelectedModelId(created.id);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "Downloaded model import failed");
    } finally {
      setIsImporting(false);
    }
  }

  function addImportedModels(importedModels: UploadedModel[]) {
    if (importedModels.length === 0) {
      return;
    }
    setModels((current) => [...importedModels, ...current]);
    setSelectedModelId(importedModels[0].id);
  }

  useEffect(() => {
    void refreshModels();
  }, []);

  return {
    addImportedModels,
    error,
    isImporting,
    isLoading,
    isUploading,
    models,
    refreshModels,
    selectedModel: models.find((model) => model.id === selectedModelId) ?? models[0] ?? null,
    selectedModelId,
    setSelectedModelId,
    submitDownloadedImport,
    submitUpload
  };
}
