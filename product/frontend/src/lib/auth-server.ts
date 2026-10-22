import "server-only";
import { NextRequest } from "next/server";
import { headers } from "next/headers";
import { getToken } from "next-auth/jwt";
import { isAuthConfigured } from "@/lib/auth-config";

export async function getBackendAccessToken(): Promise<string | null> {
  if (!isAuthConfigured()) return null;
  const requestHeaders = new Headers(await headers());
  // Authenticate browser sessions through encrypted HttpOnly cookies only.
  requestHeaders.delete("authorization");
  const token = await getToken({
    req: new NextRequest(process.env.NEXTAUTH_URL!, {
      headers: requestHeaders,
    }),
    secret: process.env.NEXTAUTH_SECRET,
    secureCookie: process.env.NEXTAUTH_URL?.startsWith("https://"),
  });
  if (
    !token ||
    typeof token.apiAccessToken !== "string" ||
    typeof token.apiAccessExpires !== "number" ||
    token.apiAccessExpires <= Date.now() / 1000
  )
    return null;
  return token.apiAccessToken;
}
