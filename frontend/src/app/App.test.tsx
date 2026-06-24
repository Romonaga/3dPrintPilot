import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(authenticatedFetch));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function authenticatedFetch(input: RequestInfo | URL): Promise<Response> {
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

function mockApiFetch(handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  return vi.mocked(globalThis.fetch).mockImplementation((input, init) => {
    if (String(input) === "/api/auth/me") {
      return authenticatedFetch(input);
    }
    return handler(input, init);
  });
}

describe("App", () => {
  it("renders the dashboard shell without making App a feature monolith", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Printers" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Find Models" })).toBeInTheDocument();
    expect(screen.getAllByText("3D Print Pilot").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Scan LAN" })).toHaveLength(2);
    expect(await screen.findByText("No saved printers yet. Scan LAN to discover printers.")).toBeInTheDocument();
    expect(screen.getByText("No compatibility checks yet.")).toBeInTheDocument();
    expect(screen.getByText("qwen3-coder:30b")).toBeInTheDocument();
    expect(screen.getByText("$5.00")).toBeInTheDocument();
    expect(screen.queryByText("Voron 2.4")).not.toBeInTheDocument();
    expect(screen.queryByText("Prusa MK4")).not.toBeInTheDocument();
    expect(screen.queryByText("Bambu X1C")).not.toBeInTheDocument();
  });

  it("discovers and imports supported Printables files from the dashboard", async () => {
    const fetchMock = mockApiFetch((input, init) => {
      const url = String(input);
      if (url === "/api/site-scanning/adapters") {
        return Promise.resolve(new Response(JSON.stringify(sampleSiteAdapters()), { status: 200 }));
      }
      if (url === "/api/models/imports/source-files/scans") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      if (url === "/api/models/imports/source-files/discover" && init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify(sampleSourceProjectFiles()), { status: 200 }));
      }
      if (url === "/api/models/imports/source-files" && init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify([sampleImportedModel()]), { status: 200 }));
      }
      return authenticatedFetch(input);
    });
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Find Models" })).toBeInTheDocument();
    expect(await screen.findByText("Runner downloads available")).toBeInTheDocument();
    expect(screen.getByLabelText("Source site")).toHaveValue("printables");

    await user.type(screen.getByLabelText("Project URL"), "https://www.printables.com/model/123-managed-triangle");
    await user.click(screen.getByRole("button", { name: "Scan Files" }));

    await waitFor(() => expect(screen.getByLabelText("Discovered source files")).toBeInTheDocument());
    expect(within(screen.getByLabelText("Discovered source files")).getByText("Managed Triangle Project")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Saved source project scans")).getByText("Managed Triangle Project")).toBeInTheDocument();
    expect(screen.getByLabelText(/triangle\.stl/i)).toBeChecked();
    expect(screen.getByLabelText(/assembly-notes\.pdf/i)).toBeDisabled();
    expect(screen.getByText("1 projects")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download Selected (1)" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Download Selected (1)" }));

    expect(await screen.findByText("Managed Triangle")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/models/imports/source-files/discover",
      expect.objectContaining({
        body: JSON.stringify({
          site_key: "printables",
          source_project_url: "https://www.printables.com/model/123-managed-triangle"
        }),
        method: "POST"
      })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/models/imports/source-files",
      expect.objectContaining({
        body: JSON.stringify({
          site_key: "printables",
          source_project_url: "https://www.printables.com/model/123-managed-triangle",
          file_ids: ["file-stl"],
          title: null
        }),
        method: "POST"
      })
    );
  });

  it("shows a clear unavailable state when no configured source runners support downloads", async () => {
    mockApiFetch((input) => {
      const url = String(input);
      if (url === "/api/site-scanning/adapters") {
        return Promise.resolve(
          new Response(JSON.stringify([{ ...sampleSiteAdapters()[0], enabled: false, supports_downloads: false }]), { status: 200 })
        );
      }
      if (url === "/api/models/imports/source-files/scans") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return authenticatedFetch(input);
    });
    render(<App />);

    expect(await screen.findByText("No enabled source site runners support managed file downloads yet.")).toBeInTheDocument();
    expect(screen.getByLabelText("Source site")).toBeDisabled();
    expect(screen.getByLabelText("Project URL")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Scan Files" })).toBeDisabled();
  });

  it("shows machine state and meaningful print progress on dashboard printer cards", async () => {
    const user = userEvent.setup();
    const fetchMock = mockApiFetch((input) => {
      const url = String(input);
      if (url === "/api/printers") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: 4,
                name: "Snapmaker U1",
                host: "192.168.1.24",
                port: 7125,
                protocol: "http",
                printer_type: "snapmaker_moonraker",
                state: "online",
                identity_key: "moonraker:snapmaker:machine_id:u1",
                adapter_type: "moonraker",
                capabilities: {
                  adapter: "moonraker",
                  job_control: true,
                  toolhead_count: 4,
                  color_count: 4,
                  nozzle_diameter_mm: 0.4
                },
                credential_configured: false,
                last_status: {},
                last_status_at: null,
                build_volume_x_mm: 320,
                build_volume_y_mm: 320,
                build_volume_z_mm: 320
              },
              {
                id: 5,
                name: "Creality K1",
                host: "192.168.1.25",
                port: 7125,
                protocol: "http",
                printer_type: "moonraker",
                state: "confirmed",
                identity_key: "moonraker:creality:k1",
                adapter_type: "moonraker",
                capabilities: { adapter: "moonraker", job_control: true },
                credential_configured: false,
                last_status: {},
                last_status_at: null,
                build_volume_x_mm: null,
                build_volume_y_mm: null,
                build_volume_z_mm: null
              },
              {
                id: 7,
                name: "Bambu A1",
                host: "192.168.1.44",
                port: 80,
                protocol: "http",
                printer_type: "mdns:bambu",
                state: "online",
                identity_key: "mdns:_bambu._tcp.local.:bambu-a1._bambu._tcp.local.",
                adapter_type: null,
                capabilities: { toolhead_count: 2 },
                credential_configured: false,
                last_status: {},
                last_status_at: null,
                build_volume_x_mm: null,
                build_volume_y_mm: null,
                build_volume_z_mm: null
              }
            ]),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/4/job-status") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              printer_id: 4,
              state: "printing",
              filename: "benchy.gcode",
              progress: 0.42,
              message: "Printing",
              bed_temperature: { current_c: 60, target_c: 65, power: 0.4 },
              toolheads: [
                {
                  name: "extruder",
                  label: "T0",
                  index: 0,
                  current_temperature: { current_c: 210, target_c: 215, power: 0.33 },
                  color: "#ff0000",
                  color_source: "vendor_object",
                  material: "PLA",
                  material_source: "vendor_object",
                  vendor: "Snapmaker",
                  subtype: "SnapSpeed"
                },
                {
                  name: "extruder1",
                  label: "T1",
                  index: 1,
                  current_temperature: { current_c: 35, target_c: 0, power: null },
                  color: null,
                  color_source: null,
                  material: null,
                  material_source: null,
                  vendor: null,
                  subtype: null
                }
              ],
              raw_status: {},
              observed_at: "2026-06-22T15:00:00Z"
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/4/files") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      if (url === "/api/printers/4/capability-diagnostics") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              printer_id: 4,
              adapter_type: "moonraker",
              extension_agents_available: false,
              extension_agents: [],
              spoolman_available: false,
              spoolman_status: null,
              probe_errors: { spoolman: "not_configured" },
              observed_at: "2026-06-22T15:00:00Z"
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/5/job-status") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              printer_id: 5,
              state: "standby",
              filename: null,
              progress: 0,
              message: null,
              raw_status: {},
              observed_at: "2026-06-22T15:00:00Z"
            }),
            { status: 200 }
          )
        );
      }
      return authenticatedFetch(input);
    });
    render(<App />);

    expect(await screen.findByText("Printing - benchy.gcode")).toBeInTheDocument();
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Print progress for Snapmaker U1" })).toHaveValue(42);
    expect(screen.getByText("320 x 320 x 320 mm")).toBeInTheDocument();
    expect(screen.getByText("4 toolheads")).toBeInTheDocument();
    expect(screen.getByText("4 colors")).toBeInTheDocument();
    expect(screen.getByText("0.4 mm nozzle")).toBeInTheDocument();
    expect(screen.getByText("2 toolheads")).toBeInTheDocument();
    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(screen.getByText("Idle")).toBeInTheDocument();
    expect(screen.getByText("Print telemetry unavailable")).toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith("/api/printers/7/job-status");

    await user.click(screen.getByRole("button", { name: "Show controls for Snapmaker U1" }));

    expect(await screen.findByLabelText("Moonraker telemetry")).toBeInTheDocument();
    expect(screen.getByText("60 C / 65 C")).toBeInTheDocument();
    expect(screen.getByText("210 C / 215 C")).toBeInTheDocument();
    expect(screen.getByText("#ff0000")).toBeInTheDocument();
    expect(screen.getByText("PLA / Snapmaker / SnapSpeed")).toBeInTheDocument();
    expect(screen.getByText("Color unknown")).toBeInTheDocument();
    expect(screen.getByText("0 extension agents")).toBeInTheDocument();
    expect(screen.getByText("Spoolman unavailable")).toBeInTheDocument();
  });

  it("toggles dark mode from the app shell", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Switch to dark mode" }));

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Switch to light mode" })).toBeInTheDocument();
  });

  it("bootstraps the first owner from the auth screen", async () => {
    const fetchMock = vi.mocked(globalThis.fetch).mockImplementation((input, init) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(
          new Response(JSON.stringify({ authenticated: false, bootstrap_required: true, user: null }), { status: 200 })
        );
      }
      if (url === "/api/auth/bootstrap") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              token: "new-token",
              expires_at: "2026-07-01T00:00:00Z",
              user: {
                id: 1,
                username: "owner",
                email: "owner@example.test",
                role: "owner",
                is_active: true,
                force_password_change: false,
                failed_login_count: 0,
                last_login_at: null
              }
            }),
            { status: 201 }
          )
        );
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Create Owner" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Username"), "owner");
    await user.type(screen.getByLabelText("Email"), "owner@example.test");
    await user.type(screen.getByLabelText("Password"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Create Owner" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/bootstrap",
      expect.objectContaining({ method: "POST" })
    );
    expect(await screen.findByRole("heading", { name: "Printers" })).toBeInTheDocument();
  });

  it("requires password change before showing the app shell", async () => {
    vi.mocked(globalThis.fetch).mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              authenticated: true,
              bootstrap_required: false,
              user: {
                id: 2,
                username: "admin",
                email: null,
                role: "admin",
                is_active: true,
                force_password_change: true,
                failed_login_count: 0,
                last_login_at: null
              }
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/auth/change-password") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: 2,
              username: "admin",
              email: null,
              role: "admin",
              is_active: true,
              force_password_change: false,
              failed_login_count: 0,
              last_login_at: null
            }),
            { status: 200 }
          )
        );
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Change Password" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Current password"), "old-password");
    await user.type(screen.getByLabelText("New password"), "new-password");
    await user.click(screen.getByRole("button", { name: "Change Password" }));

    expect(await screen.findByRole("heading", { name: "Printers" })).toBeInTheDocument();
  });

  it("lazy-loads the site scanning domain page from navigation", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Site Scans" }));

    expect(await screen.findByRole("heading", { name: "Scan Source" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Limits" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Scan Metrics" })).toBeInTheDocument();
  });

  it("keeps visited view state mounted when navigating away and back", async () => {
    mockApiFetch((input) => {
      const url = String(input);
      if (url === "/api/site-scanning/adapters") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      if (url === "/api/models") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return authenticatedFetch(input);
    });
    const user = userEvent.setup();
    render(<App />);

    expect(screen.queryByRole("heading", { name: "Upload Model" })).not.toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Site Scans" }));
    const sourceUrl = await screen.findByLabelText("Source URL");
    await user.clear(sourceUrl);
    await user.type(sourceUrl, "https://example.test/models");

    await user.click(screen.getByRole("button", { name: "Models" }));

    expect(await screen.findByRole("heading", { name: "Upload Model" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Scan Source" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Site Scans" }));

    expect(await screen.findByDisplayValue("https://example.test/models")).toBeInTheDocument();
  });

  it("lazy-loads the models page from navigation", async () => {
    mockApiFetch((input) => {
      if (String(input) === "/api/models") {
        return Promise.resolve(new Response(JSON.stringify(sampleModels()), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Models" }));

    expect(await screen.findByRole("heading", { name: "Upload Model" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Model Library" })).toBeInTheDocument();
    expect(screen.getAllByText("Calibration Cube")).toHaveLength(2);
    expect(screen.getByText("1,024")).toBeInTheDocument();
  });

  it("links model source accounts with browser capture without collecting Google passwords", async () => {
    mockApiFetch((input, init) => {
      const url = String(input);
      if (url === "/api/resources/status") {
        return authenticatedFetch(input);
      }
      if (url === "/api/settings/features") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              openai_fallback_enabled: false,
              openai_fallback_model: "gpt-5.4",
              ai_quality_threshold: 0.72,
              openai_monthly_budget_usd: "5.00",
              openai_single_request_budget_usd: "0.25",
              cost_reconciliation_required: true,
              local_ai_provider: "ollama",
              local_ai_default_model: "qwen"
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/settings/provider-secrets") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      if (url === "/api/settings/auth") {
        if (init?.method === "PUT") {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                session_timeout_minutes: JSON.parse(String(init.body)).session_timeout_minutes,
                min_session_timeout_minutes: 5,
                max_session_timeout_minutes: 43200
              }),
              { status: 200 }
            )
          );
        }
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
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                site_key: "printables",
                display_name: "Printables public model pages",
                support_level: "partial",
                capabilities: ["public_scan", "account_setup", "project_lookup"],
                setup_required: false,
                base_url: "https://www.printables.com/",
                login_url: "https://www.printables.com/login",
                enabled: true,
                supports_downloads: false,
                supported_auth_modes: ["none", "username_password", "browser_session"],
                auth_storage_notes: "Google login must use browser-assisted session linking.",
                allowed_hosts: ["printables.com", "www.printables.com"],
                default_limits: {},
                robots_terms_notes: "metadata only"
              }
            ]),
            { status: 200 }
          )
        );
      }
      if (url === "/api/site-scanning/auth-profiles") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                site_key: "printables",
                display_name: "Printables public model pages",
                auth_mode: "none",
                label: null,
                account_identifier: null,
                masked_account_identifier: null,
                header_name: null,
                configured: false,
                enabled: false,
                auth_ready: false,
                link_status: "public_only",
                link_status_message: "Public scans can run without an account. Link an account for authenticated access.",
                masked_value: null,
                updated_at: null
              }
            ]),
            { status: 200 }
          )
        );
      }
      if (url === "/api/site-scanning/auth-profiles/printables/link") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              site_key: "printables",
              display_name: "Printables public model pages",
              auth_mode: "browser_session",
              login_url: "https://www.printables.com/login",
              account_identifier: null,
              instructions: ["Open the site login page.", "Paste only the Printables session value."],
              storage_notes: "No Google password is stored."
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/site-scanning/auth-profiles/printables/browser-link") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              site_key: "printables",
              display_name: "Printables public model pages",
              auth_mode: "browser_session",
              session_id: "session-1",
              status: "running",
              message: "Login browser launched. Complete site sign-in, then capture the signed-in session.",
              login_url: "https://www.printables.com/login",
              expires_at: "2026-06-22T17:00:00Z",
              cookie_count: 0,
              auth_profile: {
                site_key: "printables",
                display_name: "Printables public model pages",
                auth_mode: "browser_session",
                label: "Personal account",
                account_identifier: "maker@example.test",
                masked_account_identifier: "m***@example.test",
                header_name: null,
                configured: false,
                enabled: true,
                auth_ready: false,
                link_status: "needs_relink",
                link_status_message: "Browser session is not stored yet.",
                masked_value: null,
                updated_at: null
              }
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/site-scanning/auth-profiles/printables/browser-link/session-1/capture") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              site_key: "printables",
              display_name: "Printables public model pages",
              auth_mode: "browser_session",
              session_id: "session-1",
              status: "linked",
              message: "Signed-in site session captured.",
              login_url: "https://www.printables.com/login",
              expires_at: "2026-06-22T17:00:00Z",
              cookie_count: 2,
              auth_profile: {
                site_key: "printables",
                display_name: "Printables public model pages",
                auth_mode: "browser_session",
                label: "Personal account",
                account_identifier: "maker@example.test",
                masked_account_identifier: "m***@example.test",
                header_name: null,
                configured: true,
                enabled: true,
                auth_ready: true,
                link_status: "linked",
                link_status_message: "Stored account link is available for unattended authenticated requests.",
                masked_value: "****abcd",
                updated_at: "2026-06-22T17:00:00Z"
              }
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/site-scanning/auth-profiles/printables/test") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              site_key: "printables",
              display_name: "Printables public model pages",
              auth_mode: "browser_session",
              auth_ready: true,
              link_status: "linked",
              message: "Stored account link is available for unattended authenticated requests.",
              configured: true,
              enabled: true,
              masked_account_identifier: "m***@example.test",
              masked_value: "****abcd",
              updated_at: "2026-06-22T17:00:00Z"
            }),
            { status: 200 }
          )
        );
      }
      return authenticatedFetch(input);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Settings" }));

    expect(await screen.findByRole("heading", { name: "Model Source Accounts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Printables public model pages" })).toBeInTheDocument();
    expect(screen.getByText("Supported setup")).toBeInTheDocument();
    expect(screen.getByText("Account setup")).toBeInTheDocument();
    expect(screen.queryByLabelText("Auth type")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Account"), "maker@example.test");
    await user.click(screen.getByRole("button", { name: "Link with browser" }));

    expect(await screen.findByText("Login browser launched. Complete site sign-in, then capture the signed-in session.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Printables session cookie/header")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Capture signed-in session" }));
    expect(await screen.findByText(/Captured 2 site cookies/)).toBeInTheDocument();
    expect(await screen.findByText("Linked")).toBeInTheDocument();
    expect(screen.queryByLabelText("Printables password")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Google password")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Advanced fallback" }));
    await user.click(screen.getByRole("button", { name: "Manual fallback" }));
    expect(await screen.findByLabelText("Printables session cookie/header")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Test connection" }));
    expect(await screen.findByText("Linked")).toBeInTheDocument();
  });

  it("opens model uploads from the dashboard Upload Model action", async () => {
    mockApiFetch((input) => {
      if (String(input) === "/api/models") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    const user = userEvent.setup();
    render(<App />);

    const uploadActions = await screen.findAllByRole("button", { name: "Upload Model" });
    await user.click(uploadActions[0]);

    expect(await screen.findByRole("heading", { name: "Upload Model" })).toBeInTheDocument();
  });

  it("lazy-loads the printers domain page from navigation", async () => {
    mockApiFetch(() => Promise.resolve(new Response(JSON.stringify([]), { status: 200 })));
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Printers" }));

    expect(await screen.findByRole("heading", { name: "Printer Actions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Saved Printers" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Add Printer" })).not.toBeInTheDocument();
  });

  it("refreshes a saved printer card without running a LAN scan", async () => {
    const fetchMock = mockApiFetch((input) => {
      const url = String(input);
      if (url === "/api/printers") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: 4,
                name: "Snapmaker U1",
                host: "192.168.1.44",
                port: 7125,
                protocol: "http",
                printer_type: "snapmaker_moonraker",
                state: "confirmed",
                identity_key: "moonraker:snapmaker:machine_id:u1",
                adapter_type: "moonraker",
                capabilities: { adapter: "moonraker", toolhead_count: 4, color_count: 4 },
                credential_configured: false,
                last_status: {},
                last_status_at: null,
                build_volume_x_mm: 320,
                build_volume_y_mm: 320,
                build_volume_z_mm: 320
              }
            ]),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/4/status") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              printer_id: 4,
              adapter_type: "moonraker",
              state: "ready",
              capabilities: { adapter: "moonraker", moonraker_version: "v0.9.0" },
              raw_status: { server: { result: { klippy_state: "ready" } } },
              observed_at: "2026-06-24T17:40:00Z"
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/4/job-status") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              printer_id: 4,
              state: "standby",
              filename: null,
              progress: 0,
              message: null,
              bed_temperature: { current_c: 27, target_c: 0, power: 0 },
              toolheads: [
                {
                  name: "extruder1",
                  label: "T1",
                  index: 1,
                  current_temperature: { current_c: 28, target_c: 0, power: 0 },
                  color: "#080a0d",
                  color_source: "vendor_object",
                  material: "PLA",
                  material_source: "vendor_object",
                  vendor: "Snapmaker",
                  subtype: "SnapSpeed"
                }
              ],
              raw_status: {},
              observed_at: "2026-06-24T17:40:00Z"
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/4/capability-diagnostics") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              printer_id: 4,
              adapter_type: "moonraker",
              extension_agents_available: false,
              extension_agents: [],
              spoolman_available: false,
              spoolman_status: null,
              probe_errors: { spoolman: "not_configured" },
              observed_at: "2026-06-24T17:40:00Z"
            }),
            { status: 200 }
          )
        );
      }
      return authenticatedFetch(input);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Printers" }));
    await user.click(await screen.findByRole("button", { name: "Refresh Snapmaker U1" }));

    expect(await screen.findByText("State: ready")).toBeInTheDocument();
    expect(screen.getByText("Job: standby (0%)")).toBeInTheDocument();
    expect(screen.getByText("T1: PLA / Snapmaker / SnapSpeed #080a0d")).toBeInTheDocument();
    expect(screen.getByText("0 extension agents / Spoolman unavailable")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/printers/4/status", expect.anything());
    expect(fetchMock).not.toHaveBeenCalledWith("/api/printers/scan", expect.anything());
  });

  it("shows Bambu MQTT telemetry from saved printer refresh without scanning", async () => {
    const fetchMock = mockApiFetch((input) => {
      const url = String(input);
      if (url === "/api/printers") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: 8,
                name: "Bambu A1",
                host: "192.168.1.53",
                port: 8883,
                protocol: "mqtts",
                printer_type: "mqtt_probe:bambu_mqtt",
                state: "confirmed",
                identity_key: "bambu:00M00A000000000",
                adapter_type: "bambu_mqtt",
                capabilities: { adapter: "bambu_mqtt" },
                credential_configured: true,
                last_status: {},
                last_status_at: null,
                build_volume_x_mm: null,
                build_volume_y_mm: null,
                build_volume_z_mm: null
              }
            ]),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/8/status") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              printer_id: 8,
              adapter_type: "bambu_mqtt",
              state: "printing",
              capabilities: { adapter: "bambu_mqtt", credential_required: true },
              raw_status: {
                source: "bambu_mqtt",
                job: { state: "printing", filename: "benchy.3mf", progress: 42 },
                temperatures: {
                  nozzle_current_c: 219.5,
                  nozzle_target_c: 220,
                  bed_current_c: 59.1,
                  bed_target_c: 60
                },
                ams: {
                  active_tray: "1",
                  trays: [
                    { id: "0", active: false, color: "#00aaff", material: "PLA" },
                    { id: "1", active: true, color: "#ff3300", material: "PLA", subtype: "Bambu PLA Matte" }
                  ]
                },
                errors: { hms: [] },
                control_enabled: false
              },
              observed_at: "2026-06-24T17:50:00Z"
            }),
            { status: 200 }
          )
        );
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Printers" }));
    await user.click(await screen.findByLabelText("Refresh Bambu A1"));

    expect(await screen.findByText("Job: printing (42%)")).toBeInTheDocument();
    expect(screen.getByText("Nozzle 220C/220C / Bed 59C/60C")).toBeInTheDocument();
    expect(screen.getByText("AMS T1 active: PLA / Bambu PLA Matte #ff3300")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/printers/8/status", expect.anything());
    expect(fetchMock).not.toHaveBeenCalledWith("/api/printers/8/job-status", expect.anything());
    expect(fetchMock).not.toHaveBeenCalledWith("/api/printers/scan", expect.anything());
  });

  it("starts a LAN scan from the dashboard Scan LAN action", async () => {
    const fetchMock = mockApiFetch((input, init) => {
      const url = String(input);
      if (url.includes("/api/printers/scan")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              summary: {
                scan_run_id: 77,
                status: "completed",
                duration_ms: 120,
                discovered_count: 1,
                method: "combined",
                scanned_host_count: 254,
                probe_count: 2540
              },
              printers: [
                {
                  name: "Bambu Lab MQTT/LAN mode",
                  host: "192.168.1.218",
                  port: 8883,
                  protocol: "tcp",
                  service_type: "tcp_probe:bambu_mqtt",
                  confidence: 82,
                  state: "discovered"
                }
              ]
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers" && (!init || init.method === undefined)) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: "Printers" });
    await user.click(screen.getAllByRole("button", { name: "Scan LAN" })[0]);

    expect(await screen.findByRole("heading", { name: "Discovered Devices" })).toBeInTheDocument();
    expect(screen.getByText("Bambu Lab MQTT/LAN mode")).toBeInTheDocument();
    expect(screen.getByText(/Bambu discovery: scan-only visibility works without credentials/)).toBeInTheDocument();
    expect(screen.getByText(/may limit Bambu Handy or cloud workflows/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/printers/scan",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("shows known scan discoveries without repeat confirm actions", async () => {
    mockApiFetch((input, init) => {
      const url = String(input);
      if (url === "/api/printers" && (!init || init.method === undefined)) {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: 7,
                name: "Bambu A1",
                host: "192.168.1.44",
                port: 80,
                protocol: "http",
                printer_type: "mdns:bambu",
                state: "online",
                identity_key: "mdns:_bambu._tcp.local.:bambu-a1._bambu._tcp.local.",
                adapter_type: null,
                capabilities: {},
                credential_configured: false,
                last_status: {},
                last_status_at: null,
                build_volume_x_mm: null,
                build_volume_y_mm: null,
                build_volume_z_mm: null
              }
            ]),
            { status: 200 }
          )
        );
      }
      if (url.includes("/api/printers/scan")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              summary: {
                scan_run_id: 89,
                status: "completed",
                duration_ms: 180,
                discovered_count: 1,
                method: "combined",
                scanned_host_count: 1,
                probe_count: 4
              },
              printers: [
                {
                  name: "Bambu A1",
                  host: "192.168.1.44",
                  port: 80,
                  protocol: "http",
                  service_type: "mdns:bambu",
                  confidence: 88,
                  state: "discovered",
                  evidence: ["mDNS service _bambu._tcp.local. advertised Bambu-A1._bambu._tcp.local."],
                  scan_result_id: 12,
                  identity_key: "mdns:_bambu._tcp.local.:bambu-a1._bambu._tcp.local.",
                  matched_printer_id: 7
                }
              ],
              groups: [
                {
                  host: "192.168.1.44",
                  name: "Bambu A1",
                  inferred_type: "Bambu Lab",
                  identity_key: "mdns:_bambu._tcp.local.:bambu-a1._bambu._tcp.local.",
                  matched_printer_id: 7,
                  confidence: 88,
                  ports: [80],
                  capabilities: ["Bambu LAN identity"],
                  endpoints: [
                    {
                      name: "Bambu A1",
                      host: "192.168.1.44",
                      port: 80,
                      protocol: "http",
                      service_type: "mdns:bambu",
                      confidence: 88,
                      state: "discovered",
                      evidence: ["mDNS service _bambu._tcp.local. advertised Bambu-A1._bambu._tcp.local."],
                      scan_result_id: 12,
                      identity_key: "mdns:_bambu._tcp.local.:bambu-a1._bambu._tcp.local.",
                      matched_printer_id: 7
                    }
                  ]
                }
              ]
            }),
            { status: 200 }
          )
        );
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Printers" }));
    expect(screen.getByText(/Bambu LAN: scan-only visibility works without credentials/)).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Scan LAN" }));

    expect(await screen.findByRole("heading", { name: "Discovered Devices" })).toBeInTheDocument();
    expect(screen.getAllByText("Bambu A1").length).toBeGreaterThan(0);
    expect(screen.getByText(/Bambu discovery: scan-only visibility works without credentials/)).toBeInTheDocument();
    expect(screen.getByText("Known")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
  });

  it("removes a known printer from the printer page context menu", async () => {
    const fetchMock = mockApiFetch((input, init) => {
      const url = String(input);
      if (url === "/api/printers" && (!init || init.method === undefined)) {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: 7,
                name: "Bambu A1",
                host: "192.168.1.44",
                port: 80,
                protocol: "http",
                printer_type: "mdns:bambu",
                state: "online",
                identity_key: "mdns:_bambu._tcp.local.:bambu-a1._bambu._tcp.local.",
                adapter_type: null,
                capabilities: {},
                credential_configured: false,
                last_status: {},
                last_status_at: null,
                build_volume_x_mm: null,
                build_volume_y_mm: null,
                build_volume_z_mm: null
              }
            ]),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/7" && init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return authenticatedFetch(input);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Printers" }));
    const savedPrinter = await screen.findByRole("article", { name: "Saved printer Bambu A1" });

    fireEvent.contextMenu(savedPrinter, { clientX: 140, clientY: 160 });

    expect(await screen.findByRole("menu", { name: "Actions for Bambu A1" })).toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Remove printer" }));

    expect(await screen.findByText("No saved printers yet.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/printers/7",
      expect.objectContaining({ method: "DELETE" })
    );
    expect(screen.queryByRole("menu", { name: "Actions for Bambu A1" })).not.toBeInTheDocument();
  });

  it("expands Moonraker file controls from dashboard cards and keeps scan inventory focused", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = mockApiFetch((input, init) => {
      const url = String(input);
      if (url === "/api/printers" && (!init || init.method === undefined)) {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: 4,
                name: "Snapmaker U1",
                host: "192.168.1.24",
                port: 7125,
                protocol: "http",
                printer_type: "snapmaker_moonraker",
                state: "online",
                identity_key: "moonraker:snapmaker:machine_id:u1",
                adapter_type: "moonraker",
                capabilities: {
                  adapter: "moonraker",
                  control_enabled: true,
                  file_management: true,
                  job_control: true,
                  raw_gcode_console: false
                },
                credential_configured: false,
                last_status: {},
                last_status_at: null,
                build_volume_x_mm: null,
                build_volume_y_mm: null,
                build_volume_z_mm: null
              },
              {
                id: 7,
                name: "Bambu A1",
                host: "192.168.1.44",
                port: 80,
                protocol: "http",
                printer_type: "mdns:bambu",
                state: "online",
                identity_key: "mdns:_bambu._tcp.local.:bambu-a1._bambu._tcp.local.",
                adapter_type: null,
                capabilities: {},
                credential_configured: false,
                last_status: {},
                last_status_at: null,
                build_volume_x_mm: null,
                build_volume_y_mm: null,
                build_volume_z_mm: null
              }
            ]),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/4/job-status") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              printer_id: 4,
              state: "printing",
              filename: "benchy.gcode",
              progress: 0.42,
              message: "Printing",
              raw_status: {},
              observed_at: "2026-06-21T16:00:00Z"
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/4/files" && (!init || init.method === undefined)) {
        return Promise.resolve(
          new Response(
            JSON.stringify([{ path: "benchy.gcode", size: 2048, modified: 1782067200, permissions: "rw" }]),
            { status: 200 }
          )
        );
      }
      if (url === "/api/printers/4/files" && init?.method === "POST") {
        return Promise.resolve(
          new Response(JSON.stringify({ printer_id: 4, action: "upload", accepted: true, raw_response: {} }), { status: 201 })
        );
      }
      if (url === "/api/printers/4/print/start" && init?.method === "POST") {
        return Promise.resolve(
          new Response(JSON.stringify({ printer_id: 4, action: "start", accepted: true, raw_response: {} }), { status: 200 })
        );
      }
      if (url === "/api/printers/4/print/cancel" && init?.method === "POST") {
        return Promise.resolve(
          new Response(JSON.stringify({ printer_id: 4, action: "cancel", accepted: true, raw_response: {} }), { status: 200 })
        );
      }
      return authenticatedFetch(input);
    });
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("Printing - benchy.gcode")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Controls for Snapmaker U1" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Show controls for Snapmaker U1" }));
    const panel = await screen.findByRole("group", { name: "Controls for Snapmaker U1" });
    expect(screen.queryByRole("group", { name: "Controls for Bambu A1" })).not.toBeInTheDocument();
    expect(await within(panel).findByText("42%")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Start" })).toBeInTheDocument();
    expect(screen.queryByText(/raw g-code/i)).not.toBeInTheDocument();

    await user.upload(within(panel).getByLabelText("Upload sliced file"), new File(["gcode"], "newfile.gcode"));
    await user.click(within(panel).getByRole("button", { name: "Upload" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/printers/4/files",
        expect.objectContaining({ method: "POST", body: expect.any(FormData) })
      )
    );
    expect(await within(panel).findByText("Uploaded newfile.gcode")).toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: "Start" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/printers/4/print/start",
        expect.objectContaining({ method: "POST" })
      )
    );
    expect(confirm).toHaveBeenCalledWith('Start print file "benchy.gcode" on Snapmaker U1?');
    expect(await within(panel).findByText("Started benchy.gcode")).toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: "Cancel" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/printers/4/print/cancel",
        expect.objectContaining({ method: "POST" })
      )
    );
    expect(confirm).toHaveBeenCalledWith("Cancel the current print on Snapmaker U1?");

    await user.click(screen.getByRole("button", { name: "Printers" }));
    expect(await screen.findByRole("heading", { name: "Printer Actions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Saved Printers" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Controls for Snapmaker U1" })).not.toBeInTheDocument();
  });

  it("keeps LAN scan results after navigating away during a pending scan", async () => {
    let resolveScan: (response: Response) => void = () => undefined;
    const pendingScan = new Promise<Response>((resolve) => {
      resolveScan = resolve;
    });
    const fetchMock = mockApiFetch((input, init) => {
      const url = String(input);
      if (url.includes("/api/printers/scan")) {
        return pendingScan;
      }
      if (url === "/api/printers" && (!init || init.method === undefined)) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      if (url === "/api/models") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Printers" }));
    await user.click(await screen.findByRole("button", { name: "Scan LAN" }));
    expect(screen.getByRole("button", { name: "Scanning" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Models" }));
    expect(await screen.findByRole("heading", { name: "Upload Model" })).toBeInTheDocument();

    resolveScan(
      new Response(
        JSON.stringify({
          summary: {
            scan_run_id: 88,
            status: "completed",
            duration_ms: 180,
            discovered_count: 1,
            method: "combined",
            scanned_host_count: 254,
            probe_count: 2540
          },
          printers: [
            {
              name: "Bambu Lab MQTT/LAN mode",
              host: "192.168.1.218",
              port: 8883,
              protocol: "tcp",
              service_type: "tcp_probe:bambu_mqtt",
              confidence: 82,
              state: "discovered"
            }
          ]
        }),
        { status: 200 }
      )
    );

    await user.click(screen.getByRole("button", { name: "Printers" }));

    expect(await screen.findByRole("heading", { name: "Discovered Devices" })).toBeInTheDocument();
    expect(screen.getByText("Bambu Lab MQTT/LAN mode")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/printers/scan",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("lazy-loads the settings page for encrypted provider secrets", async () => {
    mockApiFetch((input, init) => {
      const url = String(input);
      if (url.includes("/api/settings/features")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              openai_fallback_enabled: false,
              openai_fallback_model: "gpt-5.4",
              ai_quality_threshold: 0.72,
              openai_monthly_budget_usd: "5.00",
              openai_single_request_budget_usd: "0.25",
              cost_reconciliation_required: true,
              local_ai_provider: "ollama",
              local_ai_default_model: "qwen3-coder:30b"
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/settings/auth") {
        if (init?.method === "PUT") {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                session_timeout_minutes: JSON.parse(String(init.body)).session_timeout_minutes,
                min_session_timeout_minutes: 5,
                max_session_timeout_minutes: 43200
              }),
              { status: 200 }
            )
          );
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              session_timeout_minutes: 120,
              min_session_timeout_minutes: 5,
              max_session_timeout_minutes: 43200
            }),
            { status: 200 }
          )
        );
      }
      if (url === "/api/site-scanning/adapters" || url === "/api/site-scanning/auth-profiles") {
        return authenticatedFetch(input);
      }
      return Promise.resolve(
        new Response(
          JSON.stringify([
            {
              provider: "openai",
              secret_name: "api_token",
              label: "OpenAI API Token",
              purpose: "Fallback calls",
              configured: false,
              masked_value: null,
              updated_at: null
            }
          ]),
          { status: 200 }
        )
      );
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Settings" }));

    expect(await screen.findByRole("heading", { name: "Provider Secrets" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI Settings" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Session Timeout" })).toBeInTheDocument();
    const timeoutInput = await screen.findByLabelText("Minutes");
    expect(timeoutInput).toHaveValue(120);
    await user.clear(timeoutInput);
    await user.type(timeoutInput, "90");
    await user.click(screen.getAllByRole("button", { name: "Save" })[0]);
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/settings/auth",
        expect.objectContaining({
          body: JSON.stringify({ session_timeout_minutes: 90 }),
          method: "PUT"
        })
      )
    );
    expect(await screen.findByText("Fallback disabled")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "OpenAI API Token" })).toBeInTheDocument();
    expect(screen.getByLabelText("New value")).toHaveAttribute("type", "password");
  });

  it("lazy-loads the AI usage page from the dashboard cost action", async () => {
    mockApiFetch((input) => {
      const url = String(input);
      if (url.includes("/api/ai/accounting/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              estimated_cost_supported: true,
              final_cost_supported: true,
              reconciliation_required: true,
              reusable_package: "local_ai_accounting",
              openai_api_token_configured: true,
              openai_account_key_configured: true
            }),
            { status: 200 }
          )
        );
      }
      if (url.includes("/api/ai/accounting/reconciliation-runs")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "View Costs" }));

    expect(await screen.findByRole("heading", { name: "OpenAI Cost Reconciliation" })).toBeInTheDocument();
    expect(screen.getByText("Account Key Ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reconcile" })).toBeInTheDocument();
  });

  it("lazy-loads the compatibility page from navigation", async () => {
    mockApiFetch(() => Promise.resolve(new Response(JSON.stringify([]), { status: 200 })));
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Compatibility" }));

    expect(await screen.findByRole("heading", { name: "Run Compatibility" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Compatibility Results" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Checks" })).toBeInTheDocument();
  });
});

function sampleModels() {
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

function sampleSiteAdapters() {
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

function sampleSourceProjectFiles() {
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
      }
    ]
  };
}

function sampleImportedModel() {
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

function sampleAiAccountingStatus() {
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

function sampleResourceStatus() {
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
