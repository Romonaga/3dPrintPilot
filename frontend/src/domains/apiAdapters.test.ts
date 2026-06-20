import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { reconcileOpenAiCosts, getAiAccountingStatus } from "./ai-usage/api/aiUsageApi";
import { runCompatibilityChecks } from "./compatibility/api/compatibilityApi";
import { downloadOperationsBackup } from "./operations/api";
import { scanPrinters } from "./printers/api/printersApi";
import { getFeatureSettings, saveProviderSecret } from "./settings/api/settingsApi";
import { createSiteScan, updateSiteAdapter } from "./site-scanning/api/siteScanningApi";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("domain API adapters", () => {
  it("validates OpenAI reconciliation dates before sending requests", async () => {
    await expect(reconcileOpenAiCosts("2026-02-31", "2026-03-01")).rejects.toThrow("Invalid reconciliation start date");
    await expect(reconcileOpenAiCosts("2026-03-02", "2026-03-01")).rejects.toThrow("end date must be after start date");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("posts valid reconciliation dates as UTC ISO timestamps", async () => {
    mockJson({
      run_id: "run-1",
      status: "completed",
      period_start: "2026-06-01T00:00:00.000Z",
      period_end: "2026-06-02T00:00:00.000Z",
      estimated_total_usd: "0.00",
      final_total_usd: null,
      event_count: 0,
      updated_event_count: 0,
      bucket_count: 0
    });

    await reconcileOpenAiCosts("2026-06-01", "2026-06-02");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      period_start: "2026-06-01T00:00:00.000Z",
      period_end: "2026-06-02T00:00:00.000Z"
    });
  });

  it("maps AI status and propagates backend errors", async () => {
    mockJson({
      estimated_cost_supported: true,
      final_cost_supported: true,
      reconciliation_required: true,
      reusable_package: "local_ai_accounting",
      openai_api_token_configured: false,
      openai_account_key_configured: false,
      openai_fallback_enabled: false,
      local_model: "qwen",
      openai_fallback_model: "gpt-5.4",
      quality_threshold: 0.72,
      monthly_budget_usd: "5.00",
      single_request_budget_usd: "0.25",
      estimated_month_to_date_usd: "0",
      budget_remaining_usd: "5.00"
    });
    const status = await getAiAccountingStatus();
    expect(status.localModel).toBe("qwen");

    mockJson({ detail: "fail" }, 500);
    await expect(getAiAccountingStatus()).rejects.toThrow("AI accounting status failed with HTTP 500");
  });

  it("uses extended timeout for LAN printer scans and maps groups", async () => {
    mockJson({
      summary: {
        scan_run_id: 1,
        status: "completed",
        duration_ms: 10,
        discovered_count: 1,
        method: "http_probe",
        scanned_host_count: 1,
        probe_count: 1
      },
      printers: [],
      groups: [
        {
          host: "192.168.1.3",
          name: "Moonraker",
          inferred_type: "Klipper",
          identity_key: "mdns:_moonraker._tcp.local.:printer._moonraker._tcp.local.",
          matched_printer_id: 9,
          confidence: 90,
          ports: [7125],
          capabilities: ["Klipper"],
          endpoints: [
            {
              name: "Moonraker",
              host: "192.168.1.3",
              port: 7125,
              protocol: "http",
              service_type: "mdns:moonraker",
              confidence: 90,
              state: "discovered",
              evidence: [],
              scan_result_id: 3,
              identity_key: "mdns:_moonraker._tcp.local.:printer._moonraker._tcp.local.",
              matched_printer_id: 9
            }
          ]
        }
      ]
    });

    const result = await scanPrinters({
      timeoutSeconds: 3,
      scanMethod: "http_probe",
      targetCidr: "192.168.1.0/24",
      maxHosts: 2,
      connectTimeoutSeconds: 0.35,
      ports: "7125"
    });

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(init?.signal).toBeInstanceOf(AbortSignal);
    expect(result.groups[0].inferredType).toBe("Klipper");
    expect(result.groups[0].identityKey).toBe("mdns:_moonraker._tcp.local.:printer._moonraker._tcp.local.");
    expect(result.groups[0].matchedPrinterId).toBe(9);
    expect(result.groups[0].endpoints[0].matchedPrinterId).toBe(9);
  });

  it("maps compatibility checks and rejects backend failures", async () => {
    mockJson({
      scan_run_id: 1,
      printer_count: 1,
      candidate_count: 1,
      check_count: 1,
      checks: [
        {
          id: 2,
          scan_result_id: 3,
          printer_id: 4,
          status: "warning",
          source_type: "metadata_only",
          confidence_label: "low",
          model_title: "Cube",
          model_url: "https://example.test/cube",
          printer_name: "MK4",
          duration_ms: 1,
          created_at: "2026-06-01T00:00:00Z",
          items: []
        }
      ]
    });
    expect((await runCompatibilityChecks(1, 5)).checks[0].confidenceLabel).toBe("low");

    mockJson({}, 404);
    await expect(runCompatibilityChecks(1, 5)).rejects.toThrow("Compatibility run failed with HTTP 404");
  });

  it("maps settings and provider secret writes", async () => {
    mockJson({
      openai_fallback_enabled: true,
      openai_fallback_model: "gpt-5.4",
      ai_quality_threshold: 0.72,
      openai_monthly_budget_usd: "5.00",
      openai_single_request_budget_usd: "0.25",
      cost_reconciliation_required: true,
      local_ai_provider: "ollama",
      local_ai_default_model: "qwen"
    });
    expect((await getFeatureSettings()).openAiFallbackEnabled).toBe(true);

    mockJson({
      provider: "openai",
      secret_name: "api_token",
      label: "OpenAI API Token",
      purpose: "Fallback",
      configured: true,
      masked_value: "****1234",
      updated_at: "2026-06-01T00:00:00Z"
    });
    expect((await saveProviderSecret("openai", "api_token", "value")).maskedValue).toBe("****1234");
  });

  it("maps site scan adapters and scan candidate metadata", async () => {
    mockJson({
      site_key: "printables",
      display_name: "Printables",
      enabled: false,
      supports_downloads: false,
      allowed_hosts: ["printables.com"],
      default_limits: {},
      robots_terms_notes: "metadata only"
    });
    expect((await updateSiteAdapter("printables", false)).enabled).toBe(false);

    mockJson({
      summary: {
        scan_run_id: 7,
        status: "completed",
        stop_reason: "completed",
        start_url: "https://example.test/model",
        normalized_start_url: "https://example.test/model",
        site_key: "metadata_only",
        max_depth: 0,
        max_pages: 1,
        max_runtime_seconds: 30,
        same_domain_only: true,
        per_host_concurrency: 1,
        queued_url_count: 1,
        scanned_url_count: 1,
        accepted_result_count: 1,
        rejected_url_count: 0,
        duration_ms: 1
      },
      candidates: [
        {
          source_url: "https://example.test/model",
          title: "Model",
          depth: 0,
          parent_url: null,
          normalized_url: "https://example.test/model",
          inclusion_reason: "metadata",
          status: "needs_file",
          confidence: 0.35,
          evidence: [],
          license: "unknown",
          attribution: "example.test",
          requirements: { material: "PLA" }
        }
      ],
      rejections: []
    });
    const scan = await createSiteScan("https://example.test/model", {
      maxDepth: 0,
      maxPages: 1,
      maxRuntimeSeconds: 30,
      sameDomainOnly: true,
      perHostConcurrency: 1
    });
    expect(scan.candidates[0].attribution).toBe("example.test");
  });

  it("downloads operations backup with a stable filename", async () => {
    const createObjectURL = vi.fn(() => "blob:backup");
    const revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    mockJson({ schema_version: 1 });

    await downloadOperationsBackup();

    expect(click).toHaveBeenCalledOnce();
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:backup");
  });
});

function mockJson(payload: unknown, status = 200) {
  vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify(payload), { status }));
}
