import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "@/components/sidebar";
import LeakageCasesPage from "@/app/(workspace)/leakage-cases/page";
import LoginPage from "@/app/login/page";
import { isAuthConfigured } from "@/lib/auth-config";
import { signIn } from "next-auth/react";

vi.mock("@/lib/backend", () => ({
  getCurrentUser: async () => ({
    id: "user",
    display_name: "Reviewer",
    email: null,
    max_upload_bytes: 100,
    organizations: [],
  }),
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/documents" }));
vi.mock("@/lib/auth-config", () => ({ isAuthConfigured: vi.fn(() => false) }));
vi.mock("next-auth/react", () => ({ signIn: vi.fn(), signOut: vi.fn() }));

describe("workspace foundation", () => {
  it("provides the workspace routes and marks the active route", () => {
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: /Documents/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: /Leakage cases/ })).toHaveAttribute(
      "href",
      "/leakage-cases",
    );
    expect(screen.getByRole("link", { name: /Settings/ })).toHaveAttribute(
      "href",
      "/settings",
    );
  });
  it("shows case provenance expectations", async () => {
    render(await LeakageCasesPage());
    expect(
      screen.getByText(/evidence needed to assess blocked scopes/),
    ).toBeInTheDocument();
    expect(screen.getByText("No organization access")).toBeInTheDocument();
  });
  it("fails closed without configured identity provider and collects no credentials", async () => {
    vi.mocked(isAuthConfigured).mockReturnValue(false);
    render(await LoginPage());
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Sign-in is not configured",
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
  it("starts the standard OIDC library login when configured", async () => {
    vi.mocked(isAuthConfigured).mockReturnValue(true);
    render(await LoginPage());
    fireEvent.click(
      screen.getByRole("button", {
        name: /Continue with your identity provider/,
      }),
    );
    expect(signIn).toHaveBeenCalledWith("oidc", { callbackUrl: "/documents" });
  });
  it("shows a safe message after provider login failure", async () => {
    render(
      await LoginPage({
        searchParams: Promise.resolve({ error: "private-provider-details" }),
      }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Sign-in could not be completed",
    );
    expect(
      screen.queryByText("private-provider-details"),
    ).not.toBeInTheDocument();
  });
});
