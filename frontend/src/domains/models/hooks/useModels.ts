import { useEffect, useState } from "react";
import { listModels, uploadModel } from "../api/modelsApi";
import { type UploadedModel, type UploadModelInput } from "../types";

export function useModels() {
  const [models, setModels] = useState<UploadedModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);

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

  useEffect(() => {
    void refreshModels();
  }, []);

  return {
    error,
    isLoading,
    isUploading,
    models,
    refreshModels,
    selectedModel: models.find((model) => model.id === selectedModelId) ?? models[0] ?? null,
    selectedModelId,
    setSelectedModelId,
    submitUpload
  };
}
