// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
vi.mock("server-only", () => ({}));
const identity = vi.hoisted(() => ({
  token: "synthetic-server-token" as string | null,
}));
vi.mock("@/lib/auth-server", () => ({
  getBackendAccessToken: async () => identity.token,
}));
import { proxyFinancial } from "@/lib/financial-proxy";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  identity.token = "synthetic-server-token";
});
const org = "00000000-0000-4000-8000-000000000001";
it("forwards bounded business facet criteria without browser credential or tenant overrides", async () => {
  vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
  const fetcher = vi.fn().mockResolvedValue(Response.json({ items: [] }));
  vi.stubGlobal("fetch", fetcher);
  const response = await proxyFinancial(
    new Request(
      "https://fixture.test/api?facet=contract&search=business%20ref&supplier=Alpha&currency=USD&missing_contract=true&current=true&after=opaque&limit=20&organization_id=evil&token=evil",
      { headers: { Authorization: "Bearer browser-token" } },
    ),
    org,
    ["exception-facets"],
  );
  expect(response.status).toBe(200);
  const [url, options] = fetcher.mock.calls[0];
  expect(url.pathname).toBe(
    `/api/v1/organizations/${org}/financial/exception-facets`,
  );
  expect(url.searchParams.get("search")).toBe("business ref");
  expect(url.searchParams.get("supplier")).toBe("Alpha");
  expect(url.searchParams.has("organization_id")).toBe(false);
  expect(url.searchParams.has("token")).toBe(false);
  expect(options.headers.get("Authorization")).toBe(
    "Bearer synthetic-server-token",
  );
  expect(response.headers.get("cache-control")).toBe("no-store");
});
it("rejects unauthenticated facet access without any backend read", async () => {
  identity.token = null;
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  expect(
    (
      await proxyFinancial(
        new Request("https://fixture.test/api?facet=supplier"),
        org,
        ["exception-facets"],
      )
    ).status,
  ).toBe(401);
  expect(fetcher).not.toHaveBeenCalled();
});
it("never turns the read-only facet route into a write or a dynamic evaluation route", async () => {
  expect(
    (
      await proxyFinancial(
        new Request("https://fixture.test/api", { method: "POST" }),
        org,
        ["exception-facets"],
      )
    ).status,
  ).toBe(405);
  expect(
    (
      await proxyFinancial(new Request("https://fixture.test/api"), org, [
        "evaluations",
        "exception-facets",
      ])
    ).status,
  ).toBe(404);
});
