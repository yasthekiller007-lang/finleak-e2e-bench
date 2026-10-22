// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
vi.mock("server-only", () => ({}));
const identity = vi.hoisted(() => ({
  token: "synthetic-server-token" as string | null,
}));
vi.mock("@/lib/auth-server", () => ({
  getBackendAccessToken: async () => identity.token,
}));
import { proxySavedViews } from "@/lib/saved-views-proxy";
const org = "00000000-0000-4000-8000-000000000001",
  id = "00000000-0000-4000-8000-000000000002";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  identity.token = "synthetic-server-token";
});
function env() {
  vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
  vi.stubEnv("NEXTAUTH_URL", "https://fixture.test");
}
function mutation(method: string, body = "{}") {
  return new Request("https://fixture.test/api", {
    method,
    headers: {
      origin: "https://fixture.test",
      "content-type": "application/json",
      Authorization: "Bearer untrusted-browser-token",
    },
    body,
  });
}
it("requires an authenticated server session", async () => {
  identity.token = null;
  const f = vi.fn();
  vi.stubGlobal("fetch", f);
  expect(
    (await proxySavedViews(new Request("https://fixture.test/api"), org))
      .status,
  ).toBe(401);
  expect(f).not.toHaveBeenCalled();
});
it.each(["?token=x", "?user_id=x", "?organization_id=x", "?after=a&after=b"])(
  "rejects tenant credential and duplicate query injection %s",
  async (query) => {
    env();
    expect(
      (
        await proxySavedViews(
          new Request("https://fixture.test/api" + query),
          org,
        )
      ).status,
    ).toBe(422);
  },
);
it.each(["POST", "PATCH", "DELETE"])(
  "enforces origin on %s",
  async (method) => {
    env();
    const request = new Request("https://fixture.test/api", {
      method,
      headers: {
        origin: "https://evil.test",
        "content-type": "application/json",
      },
      body: "{}",
    });
    expect(
      (await proxySavedViews(request, org, method === "POST" ? undefined : id))
        .status,
    ).toBe(403);
  },
);
it.each(["POST", "PATCH", "DELETE"])(
  "bounds %s and uses only server-held bearer",
  async (method) => {
    env();
    const f = vi.fn().mockResolvedValue(Response.json({ ok: true }));
    vi.stubGlobal("fetch", f);
    const selected = method === "POST" ? undefined : id;
    const result = await proxySavedViews(mutation(method), org, selected);
    expect(result.status).toBe(200);
    expect(f.mock.calls[0][1].headers.get("Authorization")).toBe(
      "Bearer synthetic-server-token",
    );
    expect(f.mock.calls[0][1].method).toBe(method);
    expect(result.headers.get("cache-control")).toBe("no-store");
    expect(
      (
        await proxySavedViews(
          mutation(method, "x".repeat(16385)),
          org,
          selected,
        )
      ).status,
    ).toBe(413);
    expect(f).toHaveBeenCalledTimes(1);
  },
);
it("keeps conflict status and never replays a write after response loss", async () => {
  env();
  const f = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        { error: { code: "SAVED_VIEW_CONFLICT" } },
        { status: 409 },
      ),
    )
    .mockRejectedValueOnce(Error("lost"));
  vi.stubGlobal("fetch", f);
  expect((await proxySavedViews(mutation("PATCH"), org, id)).status).toBe(409);
  expect((await proxySavedViews(mutation("PATCH"), org, id)).status).toBe(503);
  expect(f).toHaveBeenCalledTimes(2);
});
it("rejects invalid identity paths, unsupported methods and query on detail", async () => {
  env();
  expect(
    (await proxySavedViews(new Request("https://fixture.test/api"), "bad"))
      .status,
  ).toBe(404);
  expect(
    (
      await proxySavedViews(
        new Request("https://fixture.test/api?search=x"),
        org,
        id,
      )
    ).status,
  ).toBe(422);
  expect((await proxySavedViews(mutation("POST"), org, id)).status).toBe(405);
});
