// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { encode } from "next-auth/jwt";
import { authOptions, isAuthConfigured } from "@/lib/auth-config";
import { getBackendAccessToken } from "@/lib/auth-server";
import { proxyDocuments } from "@/lib/backend-proxy";

const requestHeaders = vi.hoisted(() => ({ current: new Headers() }));
vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  headers: async () => requestHeaders.current,
}));
const organizationId = "00000000-0000-4000-8000-000000000001";
const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubEnv("NEXTAUTH_URL", "https://app.example.test");
  vi.stubEnv("NEXTAUTH_SECRET", crypto.randomUUID() + crypto.randomUUID());
  vi.stubEnv("OIDC_ISSUER_URL", "https://identity.example.test/");
  vi.stubEnv("OIDC_CLIENT_ID", "fixture-client");
  vi.stubEnv("OIDC_CLIENT_SECRET", crypto.randomUUID());
  vi.stubEnv("OIDC_AUDIENCE", "financial-leakage-api");
  vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
  requestHeaders.current = new Headers();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
async function session(expires = Date.now() / 1000 + 300) {
  const encrypted = await encode({
    token: { apiAccessToken: "fixture-api-token", apiAccessExpires: expires },
    secret: process.env.NEXTAUTH_SECRET!,
  });
  requestHeaders.current.set(
    "cookie",
    `__Secure-next-auth.session-token=${encrypted}`,
  );
  return encrypted;
}
function request(method = "GET", origin = "https://app.example.test") {
  return new Request(
    `https://app.example.test/api/organizations/${organizationId}/documents?limit=10&evil=ignore`,
    {
      method,
      headers: {
        origin,
        "content-type": "multipart/form-data; boundary=fixture",
        Authorization: "Bearer browser-forgery",
      },
      ...(method === "POST" ? { body: "fixture multipart bytes" } : {}),
    },
  );
}

describe("OIDC browser session boundary", () => {
  it("requires configuration and rejects HTTP production identity providers", () => {
    expect(isAuthConfigured()).toBe(true);
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("OIDC_ISSUER_URL", "http://localhost:9000");
    expect(isAuthConfigured()).toBe(false);
    vi.stubEnv("OIDC_CLIENT_SECRET", "");
    expect(isAuthConfigured()).toBe(false);
  });
  it("uses discovery, PKCE, state, nonce and configured API audience", () => {
    expect(authOptions().providers[0]).toMatchObject({
      type: "oauth",
      wellKnown:
        "https://identity.example.test/.well-known/openid-configuration",
      checks: ["pkce", "state", "nonce"],
      authorization: { params: { audience: "financial-leakage-api" } },
    });
  });
  it("supports scope-based API selection without a provider-specific audience parameter", () => {
    vi.stubEnv("OIDC_AUDIENCE", "");
    vi.stubEnv("OIDC_SCOPES", "openid profile api.documents");
    expect(authOptions().providers[0]).toMatchObject({
      authorization: { params: { scope: "openid profile api.documents" } },
    });
    const provider = authOptions().providers[0];
    expect(
      "authorization" in provider && JSON.stringify(provider.authorization),
    ).not.toContain("audience");
  });
  it("decrypts session cookies but ignores Authorization as a session substitute", async () => {
    const encrypted = await session();
    expect(await getBackendAccessToken()).toBe("fixture-api-token");
    requestHeaders.current = new Headers({
      Authorization: `Bearer ${encrypted}`,
    });
    expect(await getBackendAccessToken()).toBeNull();
  });
  it("rejects tampered and expired sessions", async () => {
    await session(Date.now() / 1000 - 1);
    expect(await getBackendAccessToken()).toBeNull();
    requestHeaders.current.set(
      "cookie",
      "__Secure-next-auth.session-token=forgery",
    );
    expect(await getBackendAccessToken()).toBeNull();
  });
  it("does not expose API tokens through public session callback", async () => {
    const callback = authOptions().callbacks!.session!;
    const publicSession = {
      expires: new Date().toISOString(),
      user: { name: "User" },
    };
    const result = await callback({
      session: publicSession,
      token: { apiAccessToken: "must-remain-server-side" },
      user: {
        id: "fixture",
        email: "fixture@example.test",
        emailVerified: null,
      },
      newSession: {},
      trigger: "update",
    });
    expect(result).toEqual(publicSession);
    expect(JSON.stringify(result)).not.toContain("must-remain-server-side");
  });
});

describe("documents browser proxy", () => {
  it("requires session before contacting backend", async () => {
    expect((await proxyDocuments(request(), organizationId)).status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("forwards only server session token and safe fields; backend authorizes tenancy", async () => {
    await session();
    fetchMock.mockResolvedValue(
      new Response('{"error":{"message":"Organization not found"}}', {
        status: 404,
        headers: {
          "content-type": "application/json",
          "set-cookie": "unsafe",
          "x-debug-token": "unsafe",
        },
      }),
    );
    const response = await proxyDocuments(request(), organizationId);
    expect(response.status).toBe(404);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.has("set-cookie")).toBe(false);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url.toString()).toBe(
      `http://127.0.0.1:8000/api/v1/organizations/${organizationId}/documents?limit=10`,
    );
    expect(options.headers.get("authorization")).toBe(
      "Bearer fixture-api-token",
    );
    expect(options.headers.has("cookie")).toBe(false);
  });
  it("rejects unsafe path inputs", async () => {
    await session();
    expect((await proxyDocuments(request(), "../admin")).status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("blocks cross-origin cookie-authenticated uploads", async () => {
    await session();
    expect(
      (
        await proxyDocuments(
          request("POST", "https://attacker.test"),
          organizationId,
        )
      ).status,
    ).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("bounds actual streamed bytes regardless of Content-Length", async () => {
    await session();
    vi.stubEnv("FLA_MAX_UPLOAD_BYTES", "1024");
    fetchMock.mockImplementation(async (_url, options: RequestInit) => {
      await new Response(options.body).arrayBuffer();
      return new Response("unreachable", { status: 201 });
    });
    const oversized = new Request("https://app.example.test/api", {
      method: "POST",
      headers: {
        origin: "https://app.example.test",
        "content-type": "multipart/form-data; boundary=fixture",
      },
      body: new Uint8Array(1049601),
    });
    expect((await proxyDocuments(oversized, organizationId)).status).toBe(413);
  });
  it("hides private connection details on network errors", async () => {
    await session();
    fetchMock.mockRejectedValue(
      new Error("private credential connection details"),
    );
    const response = await proxyDocuments(request(), organizationId);
    expect(response.status).toBe(503);
    expect(await response.text()).not.toContain("credential");
  });
});
