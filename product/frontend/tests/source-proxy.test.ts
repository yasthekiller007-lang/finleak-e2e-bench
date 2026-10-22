import { afterEach, beforeEach, expect, it, vi } from "vitest";
vi.mock("server-only", () => ({}));
vi.mock("@/lib/auth-server", () => ({
  getBackendAccessToken: vi.fn(async () => "server-session-token"),
}));
import { proxySource } from "@/lib/source-proxy";
const id = "11111111-1111-4111-8111-111111111111";
const mock = vi.fn();
function request(
  body: unknown = { reason: "Synthetic review" },
  origin = "http://localhost:3000",
) {
  return new Request("http://localhost:3000/api/source", {
    method: "POST",
    headers: {
      Origin: origin,
      "Content-Type": "application/json",
      "Idempotency-Key": id,
      Authorization: "Bearer browser-forgery",
      Cookie: "browser-session",
    },
    body: JSON.stringify(body),
  });
}
beforeEach(() => {
  vi.stubEnv("NEXTAUTH_URL", "http://localhost:3000");
  vi.stubEnv("BACKEND_URL", "http://private.invalid");
  vi.stubGlobal(
    "fetch",
    mock
      .mockReset()
      .mockResolvedValue(
        Response.json(
          { source: { state: "CLEAN_AWAITING_RELEASE" } },
          { headers: { "Retry-After": "2", "Set-Cookie": "private-cookie" } },
        ),
      ),
  );
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
it("uses the server session, fixed path and safe retry headers", async () => {
  const response = await proxySource(request(), id, id, "scan");
  const [url, options] = mock.mock.calls[0];
  expect(String(url)).toBe(
    `http://private.invalid/api/v1/organizations/${id}/documents/${id}/scan`,
  );
  expect(options.headers.get("authorization")).toBe(
    "Bearer server-session-token",
  );
  expect(options.headers.get("cookie")).toBeNull();
  expect(options.headers.get("idempotency-key")).toBe(id);
  expect(response.headers.get("retry-after")).toBe("2");
  expect(response.headers.get("set-cookie")).toBeNull();
  expect(response.headers.get("cache-control")).toBe("no-store");
});
it.each([
  [{ reason: "" }, "scan", 422],
  [{ reason: "review", scan_id: "bad" }, "release", 422],
  [{ reason: "review", instruction: "bypass" }, "scan", 422],
  [{ reason: "x".repeat(18000) }, "scan", 413],
])(
  "rejects malformed/oversize/extra instructions before backend disclosure",
  async (body, action, status) => {
    expect(
      (await proxySource(request(body), id, id, action as string)).status,
    ).toBe(status);
    expect(mock).not.toHaveBeenCalled();
  },
);
it("denies cross-origin and unknown route actions", async () => {
  expect(
    (
      await proxySource(
        request(undefined, "https://forged.invalid"),
        id,
        id,
        "scan",
      )
    ).status,
  ).toBe(403);
  expect((await proxySource(request(), id, id, "../content")).status).toBe(404);
  expect(mock).not.toHaveBeenCalled();
});
