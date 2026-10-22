/** Server route mocks verify existing redirects only; no real OIDC session. */
import { expect, it, vi } from "vitest";
import { demoUser } from "@/lib/product-demo";
const mocks = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  redirect: vi.fn((path: string) => {
    throw Error("REDIRECT " + path);
  }),
}));
vi.mock("@/lib/backend", () => ({ getCurrentUser: mocks.getCurrentUser }));
vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));
import { ProductWorkspacePage } from "@/components/product-workspace-page";
it("redirects an unauthenticated view using the existing login behavior", async () => {
  mocks.getCurrentUser.mockResolvedValue(null);
  await expect(
    ProductWorkspacePage({
      view: "anomalies",
      searchParams: Promise.resolve({
        org: "not-authority",
        token: "untrusted",
      }),
    }),
  ).rejects.toThrow("REDIRECT /login");
  expect(mocks.redirect).toHaveBeenCalledWith("/login");
});
it("retains duplicate parameters for strict client rejection rather than picking one", async () => {
  mocks.getCurrentUser.mockResolvedValue(demoUser);
  const element = await ProductWorkspacePage({
    view: "review",
    searchParams: Promise.resolve({
      ev: "1",
      org: [demoUser.organizations[0].id, "unknown"],
    }),
  });
  expect(element.props.initialSearch).toMatch(/org=.*&org=unknown/);
  expect(element.props.user).toBe(demoUser);
});
