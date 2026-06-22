import { useEffect, useState } from "react";
import { discoverSourceModelFiles, importSourceModelFiles, listSourceProjectScans } from "../../models/api/modelsApi";
import { type SourceProjectFiles, type UploadedModel } from "../../models/types";
import { listSiteAdapters } from "../../site-scanning/api/siteScanningApi";
import { type SiteAdapter } from "../../site-scanning/types";

type UseSupportedSourceImportOptions = {
  siteKey?: string;
  onImported?: (models: UploadedModel[]) => void;
};

export function useSupportedSourceImport({ siteKey, onImported }: UseSupportedSourceImportOptions = {}) {
  const [selectedSiteKey, setSelectedSiteKey] = useState(siteKey ?? "");
  const [projectUrl, setProjectUrl] = useState("");
  const [title, setTitle] = useState("");
  const [sourceFiles, setSourceFiles] = useState<SourceProjectFiles | null>(null);
  const [recentScans, setRecentScans] = useState<SourceProjectFiles[]>([]);
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
    Promise.all([listSiteAdapters(), listSourceProjectScans()])
      .then(([sites, scans]) => {
        if (active) {
          const capableSites = sites.filter(isConfiguredDownloadRunner);
          setSiteAdapters(sites);
          setRecentScans(scans);
          setSelectedSiteKey((current) => {
            if (current && capableSites.some((candidate) => candidate.siteKey === current)) {
              return current;
            }
            return siteKey ?? capableSites[0]?.siteKey ?? "";
          });
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
  }, [siteKey]);

  function resetSourceSelection() {
    setSourceFiles(null);
    setSelectedFileIds([]);
    setSourceError(null);
    setTitle("");
  }

  function updateSelectedSite(siteKeyValue: string) {
    setSelectedSiteKey(siteKeyValue);
    setProjectUrl("");
    resetSourceSelection();
  }

  function updateProjectUrl(value: string) {
    setProjectUrl(value);
    resetSourceSelection();
  }

  function loadRecentScan(scan: SourceProjectFiles) {
    setSelectedSiteKey(scan.siteKey);
    setProjectUrl(scan.sourceProjectUrl);
    setSourceFiles(scan);
    setSelectedFileIds(scan.files.filter((sourceFile) => sourceFile.supportedModelFile).map((sourceFile) => sourceFile.fileId));
    setSourceError(null);
    setTitle("");
  }

  async function discover() {
    if (!selectedSiteKey) {
      setSourceError("Select a configured source site first.");
      return null;
    }
    setIsDiscovering(true);
    setSourceError(null);
    try {
      const discovered = await discoverSourceModelFiles({ siteKey: selectedSiteKey, sourceProjectUrl: projectUrl });
      setSourceFiles(discovered);
      setRecentScans((current) => [discovered, ...current.filter((scan) => scan.scanId !== discovered.scanId)].slice(0, 20));
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
    if (selectedFileIds.length === 0 || !selectedSiteKey) {
      return [];
    }
    setIsImporting(true);
    setSourceError(null);
    try {
      const created = await importSourceModelFiles({
        siteKey: selectedSiteKey,
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

  const supportedSites = siteAdapters.filter(isConfiguredDownloadRunner);
  const activeSite = supportedSites.find((site) => site.siteKey === selectedSiteKey) ?? null;

  return {
    activeSite,
    discover,
    importedModels,
    importSelected,
    isDiscovering,
    isImporting,
    isLoadingSites,
    loadRecentScan,
    projectUrl,
    recentScans,
    selectedFileIds,
    selectedSiteKey,
    setTitle,
    siteError,
    sourceError,
    sourceFiles,
    supportedSites,
    title,
    toggleFile,
    updateProjectUrl,
    updateSelectedSite
  };
}

function isConfiguredDownloadRunner(site: SiteAdapter) {
  return (
    site.enabled &&
    site.supportLevel !== "generic_only" &&
    site.supportsDownloads &&
    site.capabilities.includes("file_listing") &&
    site.capabilities.includes("file_download")
  );
}
