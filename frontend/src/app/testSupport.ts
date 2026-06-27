import { vi } from "vitest";

export function authenticatedFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  if (url === "/api/auth/me") {
    return Promise.resolve(
      new Response(
        JSON.stringify({
          authenticated: true,
          bootstrap_required: false,
          user: {
            id: 1,
            username: "owner",
            email: null,
            role: "owner",
            is_active: true,
            force_password_change: false,
            failed_login_count: 0,
            last_login_at: null
          }
        }),
        { status: 200 }
      )
    );
  }
  if (url === "/api/printers") {
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  }
  if (url === "/api/compatibility/checks") {
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  }
  if (url === "/api/ai/accounting/status") {
    return Promise.resolve(new Response(JSON.stringify(sampleAiAccountingStatus()), { status: 200 }));
  }
  if (url === "/api/resources/status") {
    return Promise.resolve(new Response(JSON.stringify(sampleResourceStatus()), { status: 200 }));
  }
  if (url === "/api/settings/auth") {
    return Promise.resolve(
      new Response(
        JSON.stringify({
          session_timeout_minutes: 20160,
          min_session_timeout_minutes: 5,
          max_session_timeout_minutes: 43200
        }),
        { status: 200 }
      )
    );
  }
  if (url === "/api/site-scanning/adapters") {
    return Promise.resolve(new Response(JSON.stringify(sampleSiteAdapters()), { status: 200 }));
  }
  if (url === "/api/site-scanning/auth-profiles") {
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  }
  if (url === "/api/models/imports/source-files/scans") {
    return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
  }
  return Promise.resolve(new Response("{}", { status: 404 }));
}

export function mockApiFetch(handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  return vi.mocked(globalThis.fetch).mockImplementation((input, init) => {
    if (String(input) === "/api/auth/me") {
      return authenticatedFetch(input);
    }
    return handler(input, init);
  });
}

export function sampleModels() {
  return [
    {
      id: 1,
      title: "Calibration Cube",
      source_url: "https://models.example/cube",
      status: "analyzed",
      created_at: "2026-06-19T00:00:00Z",
      updated_at: "2026-06-19T00:00:00Z",
      files: [
        {
          id: 2,
          filename: "cube.stl",
          content_type: "model/stl",
          file_format: "stl",
          size_bytes: 4096,
          storage_status: "metadata_only",
          analysis_status: "completed",
          analysis_job_id: 9,
          analysis_warnings: [],
          geometry: {
            units: "millimeter",
            size_x_mm: 20,
            size_y_mm: 20,
            size_z_mm: 20,
            min_x_mm: 0,
            min_y_mm: 0,
            min_z_mm: 0,
            max_x_mm: 20,
            max_y_mm: 20,
            max_z_mm: 20,
            volume_mm3: 8000,
            triangle_count: 1024,
            warnings: []
          },
          created_at: "2026-06-19T00:00:00Z"
        }
      ]
    }
  ];
}

export function sampleSiteAdapters() {
  return [
    {
      site_key: "printables",
      display_name: "Printables",
      support_level: "managed",
      capabilities: ["public_scan", "account_setup", "project_lookup", "file_listing", "file_download"],
      setup_required: false,
      base_url: "https://www.printables.com/",
      login_url: "https://www.printables.com/login",
      enabled: true,
      supports_downloads: true,
      supported_auth_modes: ["none", "browser_session"],
      auth_storage_notes: "Browser session linking is supported for account downloads.",
      allowed_hosts: ["printables.com", "www.printables.com"],
      default_limits: {},
      robots_terms_notes: "Use managed runner limits."
    }
  ];
}

export function sampleSourceProjectFiles() {
  return {
    scan_id: 33,
    site_key: "printables",
    source_project_url: "https://www.printables.com/model/123-managed-triangle",
    external_project_id: "123",
    project_title: "Managed Triangle Project",
    scanned_at: "2026-06-22T19:00:00Z",
    files: [
      {
        file_id: "file-stl",
        filename: "triangle.stl",
        file_format: "stl",
        size_bytes: 2048,
        source_file_url: "https://www.printables.com/model/123/files/triangle.stl",
        supported_model_file: true,
        created_at: null,
        notes: null
      },
      {
        file_id: "file-pdf",
        filename: "assembly-notes.pdf",
        file_format: "pdf",
        size_bytes: 4096,
        source_file_url: "https://www.printables.com/model/123/files/assembly-notes.pdf",
        supported_model_file: false,
        created_at: null,
        notes: "Unsupported documentation file."
      },
      {
        file_id: "download-pack-all",
        filename: "Download all files.zip",
        file_format: "zip",
        size_bytes: 8192,
        source_file_url: "https://www.printables.com/model/123/files#download-pack-all",
        supported_model_file: true,
        created_at: null,
        notes: "Printables download-all archive; supported STL and 3MF files will be imported."
      }
    ]
  };
}

export function sampleSiteScanResult() {
  return {
    summary: {
      scan_run_id: 44,
      status: "completed",
      stop_reason: "completed",
      start_url: "https://www.printables.com/model/123-managed-triangle",
      normalized_start_url: "https://www.printables.com/model/123-managed-triangle",
      site_key: "printables",
      max_depth: 0,
      max_pages: 1,
      max_runtime_seconds: 30,
      same_domain_only: true,
      per_host_concurrency: 1,
      queued_url_count: 1,
      scanned_url_count: 1,
      accepted_result_count: 1,
      rejected_url_count: 0,
      duration_ms: 25
    },
    candidates: [
      {
        source_url: "https://www.printables.com/model/123-managed-triangle",
        title: "Managed Triangle",
        depth: 0,
        parent_url: null,
        normalized_url: "https://www.printables.com/model/123-managed-triangle",
        inclusion_reason: "public_printables_metadata",
        status: "needs_file",
        confidence: 0.9,
        evidence: ["Extracted from public Printables page metadata."],
        license: "unknown",
        attribution: "Printables",
        requirements: {}
      }
    ],
    rejections: []
  };
}

export function sampleImportedModel() {
  return {
    id: 22,
    title: "Managed Triangle",
    source_url: "https://www.printables.com/model/123-managed-triangle",
    status: "stored",
    created_at: "2026-06-22T19:00:00Z",
    updated_at: "2026-06-22T19:00:00Z",
    files: [
      {
        id: 23,
        filename: "triangle.stl",
        content_type: "model/stl",
        file_format: "stl",
        size_bytes: 2048,
        storage_status: "stored",
        analysis_status: "queued",
        analysis_job_id: null,
        analysis_warnings: [],
        geometry: null,
        payload: {
          source_project_url: "https://www.printables.com/model/123-managed-triangle",
          source_file_url: "https://www.printables.com/model/123/files/triangle.stl",
          compression: "gzip",
          original_size_bytes: 2048,
          compressed_size_bytes: 1024,
          original_sha256: "original",
          compressed_sha256: "compressed",
          created_at: "2026-06-22T19:00:00Z"
        },
        created_at: "2026-06-22T19:00:00Z"
      }
    ]
  };
}

export function sampleAiAccountingStatus() {
  return {
    estimated_cost_supported: true,
    final_cost_supported: true,
    reconciliation_required: true,
    reusable_package: "local_ai_accounting",
    openai_api_token_configured: false,
    openai_account_key_configured: false,
    openai_fallback_enabled: false,
    local_model: "qwen3-coder:30b",
    openai_fallback_model: "gpt-5.4",
    quality_threshold: 0.72,
    monthly_budget_usd: "5.00",
    single_request_budget_usd: "0.25",
    estimated_month_to_date_usd: "0",
    budget_remaining_usd: "5.00"
  };
}

export function sampleResourceStatus() {
  return {
    cpu: { cores: 32, load_average: [0.1, 0.2, 0.3] },
    memory: { total_bytes: null, available_bytes: null, used_percent: 41 },
    gpu: {
      available: false,
      name: null,
      utilization_percent: null,
      memory_used_mib: null,
      memory_total_mib: null,
      memory_used_percent: null,
      temperature_c: null,
      error: "not available"
    },
    queues: {},
    ollama: null,
    local_llm: null
  };
}
