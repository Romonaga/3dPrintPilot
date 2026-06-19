import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";
import { navItems } from "../app/navigation";

describe("AppShell", () => {
  it("renders user context and wires shell actions", async () => {
    const user = userEvent.setup();
    const onLogout = vi.fn();
    const onRouteChange = vi.fn();
    const onThemeToggle = vi.fn();

    render(
      <AppShell
        activeRoute="printers"
        isDarkMode={false}
        navItems={navItems}
        user={{
          id: 7,
          username: "owner",
          email: null,
          role: "owner",
          isActive: true,
          forcePasswordChange: false,
          failedLoginCount: 0,
          lastLoginAt: null
        }}
        onLogout={onLogout}
        onRouteChange={onRouteChange}
        onThemeToggle={onThemeToggle}
      >
        <section aria-label="Current page">Shell content</section>
      </AppShell>
    );

    expect(screen.getByText("owner / owner")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Printers" })).toHaveClass("active");
    expect(screen.getByLabelText("Current page")).toHaveTextContent("Shell content");

    await user.click(screen.getByRole("button", { name: "Models" }));
    await user.click(screen.getByRole("button", { name: "Switch to dark mode" }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(onRouteChange).toHaveBeenCalledWith("models");
    expect(onThemeToggle).toHaveBeenCalledTimes(1);
    expect(onLogout).toHaveBeenCalledTimes(1);
  });
});
