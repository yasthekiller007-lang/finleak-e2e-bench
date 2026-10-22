// @vitest-environment node
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { proxyFinancial } from "@/lib/financial-proxy";
import { money, evidencePaths } from "@/lib/financial";
vi.mock("server-only", () => ({}));
const auth = vi.hoisted(() => ({
  token: "private-server-token" as string | null,
}));
vi.mock("@/lib/auth-server", () => ({
  getBackendAccessToken: async () => auth.token,
}));
const org = "00000000-0000-4000-8000-000000000001";
const source = "00000000-0000-4000-8000-000000000002";
const fetchMock = vi.fn();
beforeEach(() => {
  auth.token = "private-server-token";
  vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
  vi.stubEnv("NEXTAUTH_URL", "https://app.example.test");
  vi.stubGlobal(
    "fetch",
    fetchMock
      .mockReset()
      .mockResolvedValue(
        Response.json({ items: [] }, { headers: { "set-cookie": "unsafe" } }),
      ),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
function request(
  method = "GET",
  origin = "https://app.example.test",
  body?: string,
) {
  return new Request(
    "https://app.example.test/api?limit=20&offset=4&evil=ignored",
    {
      method,
      body,
      headers: {
        origin,
        "Content-Type": "application/json",
        Authorization: "Bearer browser-forgery",
        "Idempotency-Key": org,
      },
    },
  );
}
it("requires a server session", async () => {
  auth.token = null;
  expect((await proxyFinancial(request(), org, ["summary"])).status).toBe(401);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("forwards only the server token and approved route parameters", async () => {
  const r = await proxyFinancial(request(), org, ["evaluations"]);
  expect(r.headers.get("cache-control")).toBe("no-store");
  expect(r.headers.has("set-cookie")).toBe(false);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url.toString()).toBe(
    `http://127.0.0.1:8000/api/v1/organizations/${org}/financial/evaluations?limit=20&offset=4`,
  );
  expect(options.headers.get("authorization")).toBe(
    "Bearer private-server-token",
  );
  expect(options.headers.has("cookie")).toBe(false);
});
it.each([
  ["sources", source, "reviews"],
  ["sources", source, "evaluate"],
  ["evaluations", source, "decision"],
])("blocks cross-origin financial mutations %s", async (...path) => {
  expect(
    (
      await proxyFinancial(
        request("POST", "https://attacker.test", "{}"),
        org,
        path,
      )
    ).status,
  ).toBe(403);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("bounds review payloads before forwarding", async () => {
  expect(
    (
      await proxyFinancial(
        request("POST", undefined, "x".repeat(1048577)),
        org,
        ["sources", source, "reviews"],
      )
    ).status,
  ).toBe(413);
  expect(fetchMock).not.toHaveBeenCalled();
});
it.each([
  ["sources", "../..", "reviews"],
  ["sources", source, "delete"],
  ["audit", source],
])("rejects unapproved paths", async (...path) => {
  const r = await proxyFinancial(request(), org, path);
  expect([404, 405]).toContain(r.status);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("retains financial decimal strings and distinguishes unknown from zero", () => {
  expect(money(null, "USD")).toBe("Not assessed");
  expect(money("0.000000", "USD")).toBe("0.00 USD");
  expect(money("99999999999999.123456", "USD")).toBe(
    "99,999,999,999,999.123456 USD",
  );
  expect(evidencePaths({ a: null, b: ["0"] })).toEqual(["/a", "/b/0"]);
});
it("forwards a safe correlation across the actual proxy and preserves retry guidance", async () => {
  const incoming = request();
  incoming.headers.set("X-Request-ID", source);
  fetchMock.mockResolvedValue(
    Response.json(
      { error: { code: "unavailable" } },
      {
        status: 503,
        headers: {
          "X-Request-ID": source,
          "Retry-After": "5",
          "set-cookie": "private",
        },
      },
    ),
  );
  const response = await proxyFinancial(incoming, org, ["summary"]);
  expect(fetchMock.mock.calls[0][1].headers.get("X-Request-ID")).toBe(source);
  expect(response.headers.get("X-Request-ID")).toBe(source);
  expect(response.headers.get("Retry-After")).toBe("5");
  expect(response.headers.get("set-cookie")).toBeNull();
  fetchMock.mockResolvedValue(
    Response.json(
      {},
      {
        headers: {
          "X-Request-ID": "private-token",
          "Retry-After": "private-token",
        },
      },
    ),
  );
  const rejected = await proxyFinancial(incoming, org, ["summary"]);
  expect(rejected.headers.get("X-Request-ID")).toBeNull();
  expect(rejected.headers.get("Retry-After")).toBeNull();
});
