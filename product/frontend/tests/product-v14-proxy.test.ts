// @vitest-environment node
import { expect, it, vi, afterEach } from "vitest";
vi.mock("server-only", () => ({}));
vi.mock("@/lib/auth-server", () => ({
  getBackendAccessToken: async () => "synthetic-server-token",
}));
import { proxyFinancial } from "@/lib/financial-proxy";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
it("forwards the new query whitelist without accepting a tenant or browser credential override", async () => {
  vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
  const fetcher = vi.fn().mockResolvedValue(Response.json({ items: [] }));
  vi.stubGlobal("fetch", fetcher);
  const org = "00000000-0000-4000-8000-000000000001";
  const req = new Request(
    "https://fixture.test/api?pagination=cursor&limit=20&after=opaque&q=demo&supplier=DEMO&currency=USD&decision_status=confirmed&created_from=2026-10-01T00%3A00%3A00Z&organization_id=evil&token=evil",
    { headers: { Authorization: "Bearer browser-forgery" } },
  );
  expect((await proxyFinancial(req, org, ["evaluations"])).status).toBe(200);
  const [url, options] = fetcher.mock.calls[0];
  expect(url.pathname).toBe(
    `/api/v1/organizations/${org}/financial/evaluations`,
  );
  expect(url.searchParams.get("after")).toBe("opaque");
  expect(url.searchParams.get("supplier")).toBe("DEMO");
  expect(url.searchParams.has("organization_id")).toBe(false);
  expect(url.searchParams.has("token")).toBe(false);
  expect(options.headers.get("authorization")).toBe(
    "Bearer synthetic-server-token",
  );
});
