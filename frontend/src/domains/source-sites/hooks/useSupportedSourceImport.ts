import { useEffect, useState } from "react";
import { discoverSourceModelFiles, importSourceModelFiles } from "../../models/api/modelsApi";
import { type SourceProjectFiles, type UploadedModel } from "../../models/types";
import { listSiteAdapters } from "../../site-scanning/api/siteScanningApi";
import { type SiteAdapter } from "../../site-scanning/types";

type UseSupportedSourceImportOptions = {
  siteKey?: string;
  onImported?: (models: UploadedModel[]) => void;
};

export function useSupportedSourceImport({ siteKey = "printables", onImported }: UseSupportedSourceImportOptions = {}) {
  const [projectUrl, setProjectUrl] = useState("");
  const [title, setTitle] = useState("");
  const [sourceFiles, setSourceFiles] = useState<SourceProjectFiles | null>(null);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [siteAdapters, setSiteAdapters] = useState<SiteAdapter[]>([]);
  const [siteError, setSiteError] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [importedModels, setImportedModels] = useState<UploadedModel[]>([]);
  const [isLoadingSites, setIsLoadingSites] = useState(true);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  useEffect(() => {
    let active = true;
    setIsLoadingSites(true);
    listSiteAdapters()
      .then((sites) => {
        if (active) {
          setSiteAdapters(sites);
          setSiteError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setSiteError(err instanceof Error ? err.message : "Source site catalog failed");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoadingSites(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  function updateProjectUrl(value: string) {
    setProjectUrl(value);
    setSourceFiles(null);
    setSelectedFileIds([]);
    setSourceError(null);
  }

  async function discover() {
    setIsDiscovering(true);
    setSourceError(null);
    try {
      const discovered = await discoverSourceModelFiles({ siteKey, sourceProjectUrl: projectUrl });
      setSourceFiles(discovered);
      setSelectedFileIds(discovered.files.filter((sourceFile) => sourceFile.supportedModelFile).map((sourceFile) => sourceFile.fileId));
      return discovered;
    } catch (err) {
      setSourceFiles(null);
      setSelectedFileIds([]);
      setSourceError(err instanceof Error ? err.message : "Source file discovery failed");
      return null;
    } finally {
      setIsDiscovering(false);
    }
  }

  async function importSelected() {
    if (selectedFileIds.length === 0) {
      return [];
    }
    setIsImporting(true);
    setSourceError(null);
    try {
      const created = await importSourceModelFiles({
        siteKey,
        sourceProjectUrl: projectUrl,
        fileIds: selectedFileIds,
        title
      });
      setImportedModels((current) => [...created, ...current]);
      onImported?.(created);
      setTitle("");
      setSelectedFileIds([]);
      setSourceFiles(null);
      return created;
    } catch (err) {
      setSourceError(err instanceof Error ? err.message : "Source file import failed");
      return [];
    } finally {
      setIsImporting(false);
    }
  }

  function toggleFile(fileId: string) {
    setSelectedFileIds((current) => (current.includes(fileId) ? current.filter((selected) => selected !== fileId) : [...current, fileId]));
  }

  const activeSite = siteAdapters.find((site) => site.siteKey === siteKey) ?? null;
  const managedSites = siteAdapters.filter((site) => site.supportLevel !== "generic_only");

  return {
    activeSite,
    discover,
    importedModels,
    importSelected,
    isDiscovering,
    isImporting,
    isLoadingSites,
    managedSites,
    projectUrl,
    selectedFileIds,
    setTitle,
    siteError,
    sourceError,
    sourceFiles,
    title,
    toggleFile,
    updateProjectUrl
  };
}
