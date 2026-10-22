import "server-only";
import type { NextAuthOptions } from "next-auth";

export function isAuthConfigured(): boolean {
  const {
    NEXTAUTH_URL,
    NEXTAUTH_SECRET,
    OIDC_ISSUER_URL,
    OIDC_CLIENT_ID,
    OIDC_CLIENT_SECRET,
  } = process.env;
  if (
    !NEXTAUTH_URL ||
    !NEXTAUTH_SECRET ||
    NEXTAUTH_SECRET.length < 32 ||
    !OIDC_ISSUER_URL ||
    !OIDC_CLIENT_ID ||
    !OIDC_CLIENT_SECRET
  )
    return false;
  try {
    for (const [index, value] of [NEXTAUTH_URL, OIDC_ISSUER_URL].entries()) {
      const url = new URL(value);
      const local =
        process.env.NODE_ENV !== "production" &&
        url.protocol === "http:" &&
        ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
      if (
        url.username ||
        url.password ||
        url.search ||
        url.hash ||
        (index === 0 && url.pathname !== "/") ||
        (url.protocol !== "https:" && !local)
      )
        return false;
    }
    return true;
  } catch {
    return false;
  }
}

export function authOptions(): NextAuthOptions {
  const issuer = process.env.OIDC_ISSUER_URL;
  const secure = process.env.NEXTAUTH_URL?.startsWith("https://") === true;
  return {
    secret: process.env.NEXTAUTH_SECRET,
    session: { strategy: "jwt", maxAge: 3600 },
    useSecureCookies: secure,
    cookies: {
      sessionToken: {
        name: `${secure ? "__Secure-" : ""}next-auth.session-token`,
        options: { httpOnly: true, sameSite: "lax", path: "/", secure },
      },
    },
    pages: { signIn: "/login", error: "/login" },
    providers: [
      {
        id: "oidc",
        name: "Organization identity provider",
        type: "oauth",
        issuer,
        wellKnown: `${issuer?.replace(/\/$/, "")}/.well-known/openid-configuration`,
        clientId: process.env.OIDC_CLIENT_ID,
        clientSecret: process.env.OIDC_CLIENT_SECRET,
        idToken: true,
        checks: ["pkce", "state", "nonce"],
        authorization: {
          params: {
            scope: process.env.OIDC_SCOPES || "openid profile email",
            ...(process.env.OIDC_AUDIENCE
              ? { audience: process.env.OIDC_AUDIENCE }
              : {}),
          },
        },
        profile(profile) {
          return {
            id: profile.sub,
            name: profile.name ?? null,
            email: profile.email ?? null,
            image: null,
          };
        },
      },
    ],
    callbacks: {
      async jwt({ token, account }) {
        if (account) {
          token.apiAccessToken = account.access_token;
          token.apiAccessExpires =
            account.expires_at ?? Math.floor(Date.now() / 1000) + 300;
        }
        return token;
      },
      // The default session response contains basic profile fields only, never API tokens.
      async session({ session }) {
        return session;
      },
    },
    logger: {
      error() {
        console.error("oidc_authentication_error");
      },
      warn() {
        console.warn("oidc_authentication_warning");
      },
      debug() {},
    },
    debug: false,
  };
}
