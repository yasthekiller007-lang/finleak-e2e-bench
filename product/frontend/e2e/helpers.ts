import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, type Page } from "@playwright/test";

export type Row = { id: string; [key: string]: unknown };
export const roster = JSON.parse(
  readFileSync("../.local/phase7/roster.json", "utf8"),
) as {
  company: string;
  other: string;
  users: Record<string, string>;
  term: Record<string, unknown>;
  billing: Record<string, unknown>;
};
export const origin = "http://127.0.0.1:3000";
export const base = `/api/organizations/${roster.company}`;
export const observations: {
  operation: string;
  latency_ms: number;
  status: number;
}[] = [];
function operationName(path: string, method: string) {
  if (path.includes("/source-status")) return "source_status";
  if (path.endsWith("/content")) return "original_download";
  if (path.endsWith("/scan")) return "scan";
  if (path.endsWith("/release")) return "source_release";
  if (path.endsWith("/process")) return "extraction";
  if (
    path.endsWith("/evaluate") ||
    (path.endsWith("/evaluations") && method === "POST")
  )
    return "evaluation";
  if (path.endsWith("/generate")) return "proof_generation";
  if (path.includes("/reviews")) return "financial_review";
  if (path.includes("/proposals")) return "recovery_proposal_or_approval";
  if (path.includes("/report")) return "recovery_report";
  if (path.includes("/recovery")) return "recovery_read_or_prepare";
  if (path.includes("/proof")) return "proof_read";
  if (path.includes("/summary")) return "financial_summary";
  if (path.endsWith("/documents") && method === "POST") return "upload";
  return method === "GET" ? "workspace_read" : "explicit_preparation";
}

export function observeOperations(page: Page) {
  page.on("requestfinished", (request) => {
    const path = new URL(request.url()).pathname;
    if (!path.startsWith(base)) return;
    const duration = request.timing().responseEnd;
    if (duration < 0) return;
    void request.response().then((response) => {
      if (response)
        observations.push({
          operation: operationName(path, request.method()),
          latency_ms: duration,
          status: response.status(),
        });
    });
  });
}

export async function login(page: Page, subject: string) {
  await page.goto("/login");
  await page
    .getByRole("button", { name: "Continue with your identity provider" })
    .click();
  await page.getByLabel("Test account").selectOption(subject);
  await page.getByRole("button", { name: "Sign in synthetic account" }).click();
  await expect(page).toHaveURL(/\/documents$/);
  const session = await page.request.get("/api/auth/session");
  const body = await session.text();
  expect(body).not.toMatch(
    /apiAccessToken|access_token|id_token|refresh_token/,
  );
  const cookie = (await page.context().cookies()).find(
    (c) => c.name === "next-auth.session-token",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Lax");
  // HTTP loopback fixture cookies do not qualify the production Secure profile.
}

export async function call(
  page: Page,
  path: string,
  body?: unknown,
  key = randomUUID(),
  operation?: string,
) {
  const start = performance.now();
  const response = await page.request.fetch(base + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { Origin: origin, "Idempotency-Key": key },
    ...(body === undefined ? {} : { data: body }),
  });
  observations.push({
    operation:
      operation ?? operationName(path, body === undefined ? "GET" : "POST"),
    latency_ms: performance.now() - start,
    status: response.status(),
  });
  expect(
    response.ok(),
    `Safe API status ${response.status()} for ${path}`,
  ).toBe(true);
  return (await response.json()) as Row;
}

export function leaves(value: unknown, prefix = ""): string[] {
  if (value !== null && typeof value === "object")
    return Object.entries(value).flatMap(([k, v]) =>
      leaves(v, `${prefix}/${k}`),
    );
  return [prefix];
}

export function rawFields(
  value: unknown,
  prefix = "/value",
): Record<string, string> {
  if (value === null || value === undefined) return {};
  if (typeof value === "object")
    return Object.assign(
      {},
      ...Object.entries(value).map(([k, v]) => rawFields(v, `${prefix}/${k}`)),
    );
  return {
    [prefix]:
      typeof value === "boolean" ? (value ? "True" : "False") : String(value),
  };
}
