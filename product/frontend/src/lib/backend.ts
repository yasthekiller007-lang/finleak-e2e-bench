import "server-only";
import { getBackendAccessToken } from "@/lib/auth-server";
import type { CurrentUser } from "@/lib/documents";

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const token = await getBackendAccessToken();
  if (!token) return null;
  const backend = process.env.BACKEND_URL;
  if (!backend) throw new Error("Account service is not configured");
  const response = await fetch(new URL("/api/v1/me", backend), {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (response.status === 401) return null;
  if (!response.ok)
    throw new Error("Account service is temporarily unavailable");
  return response.json() as Promise<CurrentUser>;
}
