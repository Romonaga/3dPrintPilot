import { useEffect, useState } from "react";
import { discoverSourceModelFiles, importDownloadedModelFile, importSourceModelFiles, listModels, uploadModel } from "../api/modelsApi";
import {
  type DiscoverSourceFilesInput,
  type ImportDownloadedModelInput,
  type ImportSourceFilesInput,
  type SourceProjectFiles,
  type UploadedModel,
  type UploadModelInput
} from "../types";

export function useModels() {
  const [models, setModels] = useState<UploadedModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isDiscoveringSourceFiles, setIsDiscoveringSourceFiles] = useState(false);
  const [isImportingSourceFiles, setIsImportingSourceFiles] = useState(false);
  const [sourceFiles, setSourceFiles] = useState<SourceProjectFiles | null>(null);
  const [sourceFileError, setSourceFileError] = useState<string | null>(null);

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

  async function discoverSourceFiles(input: DiscoverSourceFilesInput) {
    setIsDiscoveringSourceFiles(true);
    setSourceFileError(null);
    try {
      const discovered = await discoverSourceModelFiles(input);
      setSourceFiles(discovered);
      return discovered;
    } catch (discoverError) {
      setSourceFiles(null);
      setSourceFileError(discoverError instanceof Error ? discoverError.message : "Source file discovery failed");
      return null;
    } finally {
      setIsDiscoveringSourceFiles(false);
    }
  }

  async function submitSourceFileImport(input: ImportSourceFilesInput) {
    setIsImportingSourceFiles(true);
    setSourceFileError(null);
    try {
      const created = await importSourceModelFiles(input);
      setModels((current) => [...created, ...current]);
      setSelectedModelId(created[0]?.id ?? null);
      return created;
    } catch (importError) {
      setSourceFileError(importError instanceof Error ? importError.message : "Source file import failed");
      return [];
    } finally {
      setIsImportingSourceFiles(false);
    }
  }

  function clearSourceFiles() {
    setSourceFiles(null);
    setSourceFileError(null);
  }

  useEffect(() => {
    void refreshModels();
  }, []);

  return {
    clearSourceFiles,
    discoverSourceFiles,
    error,
    isDiscoveringSourceFiles,
    isImporting,
    isImportingSourceFiles,
    isLoading,
    isUploading,
    models,
    refreshModels,
    selectedModel: models.find((model) => model.id === selectedModelId) ?? models[0] ?? null,
    selectedModelId,
    setSelectedModelId,
    sourceFileError,
    sourceFiles,
    submitDownloadedImport,
    submitSourceFileImport,
    submitUpload
  };
}
