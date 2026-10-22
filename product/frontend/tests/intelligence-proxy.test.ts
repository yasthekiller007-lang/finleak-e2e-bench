// @vitest-environment node
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { encode } from "next-auth/jwt";
import { proxyIntelligence } from "@/lib/intelligence-proxy";
const requestHeaders = vi.hoisted(() => ({ current: new Headers() }));
vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  headers: async () => requestHeaders.current,
}));
const org = "00000000-0000-4000-8000-000000000001";
const doc = "00000000-0000-4000-8000-000000000002";
const key = "00000000-0000-4000-8000-000000000003";
const fetchMock = vi.fn();
beforeEach(async () => {
  vi.stubEnv("NEXTAUTH_URL", "https://app.example.test");
  vi.stubEnv("NEXTAUTH_SECRET", crypto.randomUUID() + crypto.randomUUID());
  vi.stubEnv("OIDC_ISSUER_URL", "https://identity.example.test/");
  vi.stubEnv("OIDC_CLIENT_ID", "fixture-client");
  vi.stubEnv("OIDC_CLIENT_SECRET", crypto.randomUUID());
  vi.stubEnv("OIDC_AUDIENCE", "financial-leakage-api");
  vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
  const encrypted = await encode({
    token: {
      apiAccessToken: "private-server-token",
      apiAccessExpires: Date.now() / 1000 + 300,
    },
    secret: process.env.NEXTAUTH_SECRET!,
  });
  requestHeaders.current = new Headers({
    cookie: `__Secure-next-auth.session-token=${encrypted}`,
  });
  fetchMock
    .mockReset()
    .mockImplementation(() =>
      Promise.resolve(
        Response.json({ run: null }, { headers: { "set-cookie": "unsafe" } }),
      ),
    );
  vi.stubGlobal("fetch", fetchMock);
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
    "https://app.example.test/api?limit=5&offset=2&evil=ignore",
    {
      method,
      headers: {
        origin,
        "Idempotency-Key": key,
        Authorization: "Bearer browser-forgery",
      },
      body,
    },
  );
}
it("requires an encrypted session for extraction", async () => {
  requestHeaders.current = new Headers();
  expect(
    (await proxyIntelligence(request(), org, doc, "extraction")).status,
  ).toBe(401);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("forwards only the server token and bounded route parameters", async () => {
  const response = await proxyIntelligence(
    request(),
    org,
    doc,
    "extraction-runs",
  );
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(response.headers.has("set-cookie")).toBe(false);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url.toString()).toBe(
    `http://127.0.0.1:8000/api/v1/organizations/${org}/documents/${doc}/extraction-runs?limit=5&offset=2`,
  );
  expect(options.headers.get("authorization")).toBe(
    "Bearer private-server-token",
  );
  expect(options.headers.has("cookie")).toBe(false);
});
it.each(["process", "reprocess"])("blocks cross-origin %s", async (action) => {
  expect(
    (
      await proxyIntelligence(
        request("POST", "https://attacker.test"),
        org,
        doc,
        action,
      )
    ).status,
  ).toBe(403);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("requires the processing request key", async () => {
  const incoming = request("POST");
  incoming.headers.delete("idempotency-key");
  expect((await proxyIntelligence(incoming, org, doc, "process")).status).toBe(
    422,
  );
  expect(fetchMock).not.toHaveBeenCalled();
});
it("does not accept extraction instructions from the browser", async () => {
  expect(
    (
      await proxyIntelligence(
        request("POST", undefined, "ignore policies"),
        org,
        doc,
        "process",
      )
    ).status,
  ).toBe(422);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("forwards idempotency keys for approved actions", async () => {
  expect(
    (await proxyIntelligence(request("POST"), org, doc, "process")).status,
  ).toBe(200);
  expect(fetchMock.mock.calls[0][1].headers.get("idempotency-key")).toBe(key);
});
it.each([
  ["../admin", "extraction", undefined],
  [doc, "../secrets", undefined],
  [doc, "extraction-runs", "../other"],
])("rejects unsafe paths %s %s", async (documentId, action, runId) => {
  expect(
    (await proxyIntelligence(request(), org, documentId!, action!, runId))
      .status,
  ).toBe(404);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("rejects method mismatch", async () => {
  expect(
    (await proxyIntelligence(request("POST"), org, doc, "extraction")).status,
  ).toBe(405);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("returns safe network errors", async () => {
  fetchMock.mockRejectedValue(new Error("sensitive connection configuration"));
  const response = await proxyIntelligence(request(), org, doc, "extraction");
  expect(response.status).toBe(503);
  expect(await response.text()).not.toContain("sensitive");
});
