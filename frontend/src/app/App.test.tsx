import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("renders the dashboard shell without making App a feature monolith", async () => {
    render(<App />);

    expect(screen.getAllByText("3D Print Pilot").length).toBeGreaterThan(0);
    expect(await screen.findByRole("heading", { name: "Printers" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Scan LAN" })).toHaveLength(2);
    expect(screen.getAllByText("Estimated")).toHaveLength(2);
    expect(screen.getByText("Final")).toBeInTheDocument();
  });

  it("toggles dark mode from the app shell", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Switch to dark mode" }));

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Switch to light mode" })).toBeInTheDocument();
  });

  it("lazy-loads the site scanning domain page from navigation", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Site Scans" }));

    expect(await screen.findByRole("heading", { name: "Scan Source" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Limits" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Scan Metrics" })).toBeInTheDocument();
  });

  it("lazy-loads the printers domain page from navigation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Printers" }));

    expect(await screen.findByRole("heading", { name: "Printer Actions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Saved Printers" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Add Printer" })).not.toBeInTheDocument();
  });

  it("starts a LAN scan from the dashboard Scan LAN action", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
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

    await user.click(screen.getAllByRole("button", { name: "Scan LAN" })[0]);

    expect(await screen.findByRole("heading", { name: "Discovered Devices" })).toBeInTheDocument();
    expect(screen.getByText("Bambu Lab MQTT/LAN mode")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/printers/scan",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("lazy-loads the settings page for encrypted provider secrets", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
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
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Settings" }));

    expect(await screen.findByRole("heading", { name: "Provider Secrets" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "OpenAI API Token" })).toBeInTheDocument();
    expect(screen.getByLabelText("New value")).toHaveAttribute("type", "password");
  });

  it("lazy-loads the AI usage page from the dashboard cost action", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
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

    await user.click(screen.getByRole("button", { name: "View Costs" }));

    expect(await screen.findByRole("heading", { name: "OpenAI Cost Reconciliation" })).toBeInTheDocument();
    expect(screen.getByText("Account Key Ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reconcile" })).toBeInTheDocument();
  });

  it("lazy-loads the compatibility page from navigation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Compatibility" }));

    expect(await screen.findByRole("heading", { name: "Run Compatibility" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Compatibility Results" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Checks" })).toBeInTheDocument();
  });
});
