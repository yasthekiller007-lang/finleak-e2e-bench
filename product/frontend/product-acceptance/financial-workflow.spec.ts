/** Prepared acceptance against existing authorized services, not executed without them. */
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { test, expect, type BrowserContext, type Page } from "@playwright/test";

type Roster = {
  synthetic: boolean;
  organization: string;
  other_organization: string;
  owner: string;
  documents: { contract: string; invoice: string };
  quotes: Record<string, string>;
  term: Record<string, unknown>;
  billing: Record<string, unknown>;
  packet: Record<string, unknown>;
};
const base = process.env.PRODUCT_FRONTEND_URL ?? "http://127.0.0.1:3000";
function required(key: string) {
  const value = process.env[key];
  if (!value)
    throw new Error("Missing synthetic acceptance credential/configuration");
  return value;
}
async function login(page: Page, persona: "OWNER" | "ANALYST") {
  const issuer = new URL(required("OIDC_ISSUER_URL"));
  await page.goto("/login");
  await page
    .getByRole("button", { name: "Continue with your identity provider" })
    .click();
  await page.waitForURL((url) => url.origin === issuer.origin);
  // Credentials belong only to synthetic accounts on this explicitly configured test issuer.
  if (new URL(page.url()).origin !== issuer.origin)
    throw new Error("Unexpected identity-provider origin");
  await page
    .getByLabel(process.env.PRODUCT_OIDC_USERNAME_LABEL ?? "Username", {
      exact: true,
    })
    .fill(required(`PRODUCT_${persona}_USERNAME`));
  await page
    .getByLabel(process.env.PRODUCT_OIDC_PASSWORD_LABEL ?? "Password", {
      exact: true,
    })
    .fill(required(`PRODUCT_${persona}_PASSWORD`));
  await page
    .getByRole("button", {
      name: process.env.PRODUCT_OIDC_SUBMIT_NAME ?? "Sign In",
      exact: true,
    })
    .click();
  await page.waitForURL(
    (url) =>
      url.origin === new URL(base).origin &&
      !url.pathname.startsWith("/api/auth/"),
  );
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Financial overview", exact: true }),
  ).toBeVisible();
}
async function call(context: BrowserContext, path: string, body?: unknown) {
  return body === undefined
    ? context.request.get(`${base}${path}`)
    : context.request.post(`${base}${path}`, {
        data: body,
        headers: {
          Origin: new URL(base).origin,
          "Content-Type": "application/json",
          "Idempotency-Key": randomUUID(),
        },
      });
}
function leaves(value: unknown, prefix = ""): string[] {
  return value !== null && typeof value === "object"
    ? Object.entries(value).flatMap(([key, v]) => leaves(v, `${prefix}/${key}`))
    : [prefix];
}
function review(
  kind: string,
  value: Record<string, unknown>,
  document: string,
  quote: string,
  state = "prepared",
  previous: string | null = null,
) {
  return {
    kind,
    key: typeof value.key === "string" ? value.key : kind,
    value,
    state,
    expected_revision: previous,
    knowledge_cutoff: new Date().toISOString(),
    reason: "DEMO Product V1.1 source meaning reviewed",
    uncertainty_resolution:
      "Synthetic explicit SKU, dates, units, tax basis and rounding profile reviewed; no extraction claim",
    evidence: [
      {
        document_id: document,
        location: "Synthetic fixture CSV, complete reviewed source",
        quote,
        field_id: null,
        manual: true,
        supports: leaves(value),
      },
    ],
  };
}

test("authenticated synthetic financial workflow with independent PostgreSQL witness", async ({
  browser,
}) => {
  const roster: Roster = JSON.parse(
    readFileSync("../.local/product-v11/roster.json", "utf8"),
  );
  expect(roster.synthetic).toBe(true);
  const owner = await browser.newContext({ baseURL: base }),
    analyst = await browser.newContext({ baseURL: base }),
    anonymous = await browser.newContext({ baseURL: base });
  const page = await owner.newPage(),
    analystPage = await analyst.newPage();
  const root = `/api/organizations/${roster.organization}/financial`;
  try {
    expect((await call(anonymous, root + "/summary")).status()).toBe(401);
    await login(page, "OWNER");
    await login(analystPage, "ANALYST");
    expect(
      (
        await call(
          owner,
          `/api/organizations/${roster.other_organization}/financial/summary`,
        )
      ).status(),
    ).toBe(404);
    const sources: Record<string, string> = {};
    for (const kind of ["contract", "invoice"] as const) {
      const response = await call(owner, root + "/sources", {
        document_id: roster.documents[kind],
        kind,
      });
      expect(response.status()).toBe(201);
      sources[kind] = (await response.json()).id;
    }
    const association = {
      contract_source_id: sources.contract,
      method: "manual",
      identifier: null,
      rationale: "DEMO explicitly reviewed invoice obligation",
    };
    const inputs: [string, string, Record<string, unknown>, string][] = [
      [sources.contract, "term", roster.term, roster.documents.contract],
      [sources.contract, "packet", roster.packet, roster.documents.contract],
      [
        sources.invoice,
        "billing_scope",
        roster.billing,
        roster.documents.invoice,
      ],
      [sources.invoice, "association", association, roster.documents.invoice],
    ];
    for (const [source, kind, value, doc] of inputs) {
      const prepared = await call(
        analyst,
        `${root}/sources/${source}/reviews`,
        review(kind, value, doc, roster.quotes[doc]),
      );
      expect(prepared.status()).toBe(201);
      const preparedId = (await prepared.json()).id;
      const rejected = await call(
        analyst,
        `${root}/sources/${source}/reviews`,
        review(kind, value, doc, roster.quotes[doc], "approved", preparedId),
      );
      expect(rejected.status()).toBe(403);
      const approved = await call(
        owner,
        `${root}/sources/${source}/reviews`,
        review(kind, value, doc, roster.quotes[doc], "approved", preparedId),
      );
      expect(approved.status()).toBe(201);
    }
    const revisions = (
      await (await call(owner, `${root}/sources/${sources.invoice}`)).json()
    ).revision_ids;
    const result = await call(
      owner,
      `${root}/sources/${sources.invoice}/evaluate`,
      { scope_key: "line-1", expected_revisions: revisions },
    );
    expect(result.status()).toBe(200);
    const evaluation = await result.json();
    expect({
      expected: evaluation.expected,
      actual: evaluation.actual,
      potential: evaluation.potential,
      currency: evaluation.currency,
    }).toEqual({
      expected: "5000.000000",
      actual: "6000.000000",
      potential: "1000.000000",
      currency: "USD",
    });
    const decisionPath = `${root}/evaluations/${evaluation.id}/decision`,
      intent = {
        status: "confirmed",
        reason:
          "DEMO 100 units at USD 60 versus approved USD 50; source evidence reviewed",
        expected_decision: null,
      };
    expect((await call(analyst, decisionPath, intent)).status()).toBe(403);
    expect(
      (await call(owner, decisionPath, { ...intent, reason: "" })).status(),
    ).toBe(422);
    await page.goto(`/invoices?org=${roster.organization}`);
    await expect(
      page.getByText("DEMO-ProductV11-invoice.csv", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "View finding", exact: true })
      .click();
    await expect(page.getByText("1,000.00 USD", { exact: true })).toBeVisible();
    await expect(
      page.getByText("DEMO-ProductV11-contract.csv", { exact: true }),
    ).toBeVisible();
    await page
      .getByLabel("Reason for decision", { exact: true })
      .fill(intent.reason);
    await page
      .getByRole("checkbox", {
        name: "I reviewed the source evidence and current assessment.",
      })
      .check();
    await page
      .getByRole("button", { name: "Record financial decision", exact: true })
      .click();
    await expect(
      page.getByText(
        "Decision recorded. Historical calculations and evidence remain unchanged.",
        { exact: true },
      ),
    ).toBeVisible();
    const persisted = await (
      await call(owner, `${root}/evaluations/${evaluation.id}`)
    ).json();
    expect(persisted.status).toBe("confirmed");
    expect(typeof persisted.decision_id).toBe("string");
    expect((await call(owner, decisionPath, intent)).status()).toBe(409);
    await page.goto(
      `/anomalies?org=${roster.organization}&assessment=${evaluation.id}`,
    );
    await page.reload();
    await page
      .getByRole("tab", { name: "Review & audit history", exact: true })
      .click();
    await expect(page.getByText(intent.reason, { exact: true })).toBeVisible();
    await expect(page.getByText(roster.owner, { exact: true })).toBeVisible();
    await page.screenshot({
      path: "../.local/product-v11/authenticated-financial-journal.png",
    });
    // The separate interpreter opens a fresh database session; no JS mock or SQLite substitute.
    const witness = spawnSync(
      required("PRODUCT_PYTHON"),
      [
        "-m",
        "acceptance.product_v11",
        "witness",
        "--evaluation",
        evaluation.id,
        "--decision",
        persisted.decision_id,
      ],
      { cwd: "../backend", env: process.env, encoding: "utf8", timeout: 15000 },
    );
    if (witness.status !== 0)
      throw new Error(
        "Independent PostgreSQL witness failed; no raw database output exported",
      );
    const journal = JSON.parse(witness.stdout);
    expect(journal.status).toBe("DATABASE_READ_PASS");
    expect(journal.decision_rows).toBe(1);
    mkdirSync("../.local/product-v11", { recursive: true });
    writeFileSync(
      "../.local/product-v11/persisted-decision.json",
      JSON.stringify(
        {
          ...journal,
          oidc_browser_session: "EXECUTED_THROUGH_CONFIGURED_TEST_ISSUER",
          browser_reload: "PASS",
          role_rejection: "PASS",
          concurrent_predecessor_rejection: "PASS",
        },
        null,
        2,
      ),
    );
    // Revoke the approved term with unchanged source values to exercise stale-input rejection.
    const history = await (
      await call(
        owner,
        `${root}/sources/${sources.contract}/history?limit=100&offset=0`,
      )
    ).json();
    const head = history.items.find(
      (r: { kind: string; key: string; state: string }) =>
        r.kind === "term" && r.key === "price" && r.state === "approved",
    );
    const changed = await call(
      owner,
      `${root}/sources/${sources.contract}/reviews`,
      review(
        "term",
        roster.term,
        roster.documents.contract,
        roster.quotes[roster.documents.contract],
        "revoked",
        head.id,
      ),
    );
    expect(changed.status()).toBe(201);
    expect(
      (
        await call(owner, decisionPath, {
          ...intent,
          expected_decision: persisted.decision_id,
        })
      ).status(),
    ).toBe(409);
    const after = await (
      await call(owner, `${root}/evaluations/${evaluation.id}`)
    ).json();
    expect(after.decision_id).toBe(persisted.decision_id);
    expect(after.potential).toBe("1000.000000");
    await page.goto("/demo/dashboard");
    await expect(page.getByRole("note")).toContainText("No live API requests");
  } finally {
    await owner.close();
    await analyst.close();
    await anonymous.close();
  }
});
