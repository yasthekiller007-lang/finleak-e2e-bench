// @vitest-environment node
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import { proxyProof } from "@/lib/proof-proxy";
vi.mock("server-only", () => ({}));
const auth = vi.hoisted(() => ({
  token: "server-private-token" as string | null,
}));
vi.mock("@/lib/auth-server", () => ({
  getBackendAccessToken: async () => auth.token,
}));
const org = "00000000-0000-4000-8000-000000000001",
  id = "00000000-0000-4000-8000-000000000002";
const fetchMock = vi.fn();
beforeEach(() => {
  auth.token = "server-private-token";
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
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
function req(method = "GET", body?: string, origin = "https://app.test") {
  return new Request("https://app.test/api?limit=100&offset=4&evil=blocked", {
    method,
    body,
    headers: {
      origin,
      "Content-Type": "application/json",
      "Idempotency-Key": id,
      Authorization: "Bearer forged-browser-token",
    },
  });
}
it("requires server authentication and scopes every forwarded path", async () => {
  auth.token = null;
  expect((await proxyProof(req(), org, ["packages", id])).status).toBe(401);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("forwards only server credentials, safe queries and bounded-resource headers", async () => {
  const result = await proxyProof(req(), org, ["packages", id, "history"]);
  const [url, options] = fetchMock.mock.calls[0];
  expect(String(url)).toBe(
    `http://127.0.0.1:8000/api/v1/organizations/${org}/proof/packages/${id}/history?limit=100&offset=4`,
  );
  expect(options.headers.get("authorization")).toBe(
    "Bearer server-private-token",
  );
  expect(options.headers.has("cookie")).toBe(false);
  expect(result.headers.get("cache-control")).toBe("no-store");
  expect(result.headers.get("Retry-After")).toBe("60");
  expect(result.headers.has("set-cookie")).toBe(false);
});
it.each(["generate", "events", "export", "successor"])(
  "blocks cross-origin mutations %s",
  async (action) => {
    const path = [
      action === "generate" ? "evaluations" : "packages",
      id,
      action,
    ];
    expect(
      (await proxyProof(req("POST", "{}", "https://attacker.test"), org, path))
        .status,
    ).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  },
);
it("forwards UUID request keys without decoding or rewriting JSON", async () => {
  const body =
    '{"expected_fingerprint":"exact-financial-hash","scale":"18.40"}';
  await proxyProof(req("POST", body), org, ["evaluations", id, "generate"]);
  const options = fetchMock.mock.calls[0][1];
  expect(options.headers.get("Idempotency-Key")).toBe(id);
  expect(new TextDecoder().decode(options.body)).toBe(body);
});
it("rejects actual oversized bytes and invalid request keys", async () => {
  expect(
    (
      await proxyProof(req("POST", "x".repeat(1048577)), org, [
        "packages",
        id,
        "events",
      ])
    ).status,
  ).toBe(413);
  const request = req("POST", "{}");
  request.headers.delete("Idempotency-Key");
  expect(
    (await proxyProof(request, org, ["packages", id, "export"])).status,
  ).toBe(422);
  expect(fetchMock).not.toHaveBeenCalled();
});
it.each([
  ["packages", "../.."],
  ["packages", id, "delete"],
  ["packages", id, "sources", "victim", "download"],
  ["share", id],
])("rejects unapproved or malformed routes", async (...path) => {
  expect([404, 405]).toContain((await proxyProof(req(), org, path)).status);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("keeps private downloads attached with safe UUID names and actual checksum", async () => {
  fetchMock.mockResolvedValue(
    new Response('{"core":{}}', {
      headers: {
        "content-type": "application/json",
        "content-disposition": "inline; filename=unsafe.html",
        "X-Artifact-SHA256": "a".repeat(64),
      },
    }),
  );
  const result = await proxyProof(req(), org, ["artifacts", id, "download"]);
  expect(result.headers.get("Content-Disposition")).toBe(
    `attachment; filename="proof-${id}.json"`,
  );
  expect(result.headers.get("Content-Security-Policy")).toBe("sandbox");
  expect(result.headers.get("X-Artifact-SHA256")).toBe("a".repeat(64));
  expect(await result.text()).toBe('{"core":{}}');
});
