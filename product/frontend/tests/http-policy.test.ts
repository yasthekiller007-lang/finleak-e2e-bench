// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import nextConfig from "../next.config";
import { authOptions, isAuthConfigured } from "@/lib/auth-config";

vi.mock("server-only", () => ({}));

describe("pilot HTTP security contract", () => {
  it("covers pages while preserving OAuth and limiting HSTS to the owned host", async () => {
    const rules = await nextConfig.headers!();
    expect(rules[0].source).toBe("/:path*");
    const headers = Object.fromEntries(
      rules[0].headers.map(({ key, value }) => [key, value]),
    );
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["Referrer-Policy"]).toBe("no-referrer");
    expect(headers["Content-Security-Policy"]).toContain(
      "frame-ancestors 'none'",
    );
    expect(headers["Content-Security-Policy"]).not.toContain("form-action");
    expect(headers["Strict-Transport-Security"]).toBe("max-age=86400");
  });

  it("uses explicit secure HttpOnly session cookies for HTTPS", () => {
    vi.stubEnv("NEXTAUTH_URL", "https://pilot.example.test");
    try {
      const options = authOptions();
      expect(options.useSecureCookies).toBe(true);
      expect(options.cookies?.sessionToken).toEqual({
        name: "__Secure-next-auth.session-token",
        options: { httpOnly: true, sameSite: "lax", path: "/", secure: true },
      });
      expect(options.session?.maxAge).toBe(3600);
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it.each([
    "https://pilot.example.test/path",
    "https://pilot.example.test?secret=hidden",
    "https://pilot.example.test#fragment",
  ])("rejects ambiguous public origin %s", (origin) => {
    vi.stubEnv("NEXTAUTH_URL", origin);
    vi.stubEnv("NEXTAUTH_SECRET", "synthetic-strong-test-secret-at-least-32");
    vi.stubEnv("OIDC_ISSUER_URL", "https://identity.example.test/realm");
    vi.stubEnv("OIDC_CLIENT_ID", "synthetic-client");
    vi.stubEnv("OIDC_CLIENT_SECRET", "synthetic-client-secret");
    try {
      expect(isAuthConfigured()).toBe(false);
    } finally {
      vi.unstubAllEnvs();
    }
  });
});
