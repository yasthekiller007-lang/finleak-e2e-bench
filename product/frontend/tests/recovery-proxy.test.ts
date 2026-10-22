// @vitest-environment node
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { proxyRecovery } from "@/lib/recovery-proxy";
vi.mock("server-only", () => ({}));
const auth = vi.hoisted(() => ({
  token: "private-server-token" as string | null,
}));
vi.mock("@/lib/auth-server", () => ({
  getBackendAccessToken: async () => auth.token,
}));
const org = "00000000-0000-4000-8000-000000000001",
  id = "00000000-0000-4000-8000-000000000002";
const fetchMock = vi.fn();
beforeEach(() => {
  auth.token = "private-server-token";
  vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
  vi.stubEnv("NEXTAUTH_URL", "https://app.test");
  vi.stubGlobal(
    "fetch",
    fetchMock
      .mockReset()
      .mockResolvedValue(
        Response.json(
          { items: [] },
          { headers: { "set-cookie": "private", "Retry-After": "60" } },
        ),
      ),
  );
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
function req(method = "GET", body?: string, origin = "https://app.test") {
  return new Request(
    "https://app.test/api?limit=100&proposals=true&evil=blocked",
    {
      method,
      body,
      headers: {
        origin,
        "Content-Type": "application/json",
        "Idempotency-Key": id,
        Authorization: "Bearer forged-browser-token",
      },
    },
  );
}
it("uses server credentials and no-store with allowlisted query fields", async () => {
  const response = await proxyRecovery(req(), org, ["cases", id, "history"]);
  const [url, options] = fetchMock.mock.calls[0];
  expect(String(url)).toBe(
    `http://127.0.0.1:8000/api/v1/organizations/${org}/recovery/cases/${id}/history?limit=100&proposals=true`,
  );
  expect(options.headers.get("authorization")).toBe(
    "Bearer private-server-token",
  );
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(response.headers.has("set-cookie")).toBe(false);
});
it("requires authentication before resolving resources", async () => {
  auth.token = null;
  expect((await proxyRecovery(req(), org, ["cases", id])).status).toBe(401);
  expect(fetchMock).not.toHaveBeenCalled();
});
it.each([
  { path: ["export"] },
  { path: ["cases", id, "export"] },
  { path: ["cases", "../foreign", "history"] },
  { path: ["vendor", id, "send"] },
])(
  "blocks unsupported recovery export and external routes %s",
  async ({ path }) => {
    expect(
      (await proxyRecovery(req(), org, path)).status,
    ).toBeGreaterThanOrEqual(400);
    expect(fetchMock).not.toHaveBeenCalled();
  },
);
it("rejects cross-origin authority commands", async () => {
  expect(
    (
      await proxyRecovery(req("POST", "{}", "https://attacker.test"), org, [
        "proposals",
        id,
        "decision",
      ])
    ).status,
  ).toBe(403);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("bounds actual request bytes without truncating financial values", async () => {
  expect(
    (await proxyRecovery(req("POST", "x".repeat(1048577)), org, ["cases"]))
      .status,
  ).toBe(413);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("preserves exact Decimal strings and request identity", async () => {
  const raw = '{"principal":"18.40","reconciliation":"UNRESOLVED"}';
  await proxyRecovery(req("POST", raw), org, ["cases", id, "proposals"]);
  const options = fetchMock.mock.calls[0][1];
  expect(new TextDecoder().decode(options.body)).toBe(raw);
  expect(options.headers.get("idempotency-key")).toBe(id);
});
