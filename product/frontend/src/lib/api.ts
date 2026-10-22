export type ServiceHealth = "ready" | "unavailable" | "unknown";

/** Server-side only, public readiness endpoint. No auth tokens or financial data. */
export async function getServiceHealth(): Promise<ServiceHealth> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return "unknown";
  try {
    const response = await fetch(new URL("/api/v1/health/ready", backendUrl), {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) return "unavailable";
    const body: unknown = await response.json();
    return typeof body === "object" &&
      body !== null &&
      "status" in body &&
      body.status === "ready"
      ? "ready"
      : "unavailable";
  } catch {
    return "unavailable";
  }
}
import "server-only";
