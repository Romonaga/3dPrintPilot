import { render, screen } from "@testing-library/react";
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
  if (String(input) === "/api/auth/me") {
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
    expect(screen.getAllByText("3D Print Pilot").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Scan LAN" })).toHaveLength(2);
    expect(screen.getAllByText("Estimated")).toHaveLength(2);
    expect(screen.getByText("Final")).toBeInTheDocument();
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
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/printers/scan",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("lazy-loads the settings page for encrypted provider secrets", async () => {
    mockApiFetch(() =>
      Promise.resolve(
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
      )
    );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Settings" }));

    expect(await screen.findByRole("heading", { name: "Provider Secrets" })).toBeInTheDocument();
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
