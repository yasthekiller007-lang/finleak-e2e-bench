/** Real services only. Preparation runs --list, never this scenario. */
import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const base = "http://127.0.0.1:3000";
const milestones: string[] = [];
function mark(check: string) {
  milestones.push(check);
  mkdirSync("../.local/p0-evidence", { recursive: true });
  writeFileSync(
    "../.local/p0-evidence/checks.json",
    JSON.stringify({ synthetic: true, observed_checks: milestones }, null, 2) +
      "\n",
  );
}
function required(key: string) {
  const value = process.env[key];
  if (!value) throw new Error("Missing isolated synthetic configuration");
  return value;
}
async function login(page: Page, persona: "OWNER" | "ANALYST") {
  await page.goto("/login");
  await page
    .getByRole("button", {
      name: "Continue with your identity provider",
      exact: true,
    })
    .click();
  await page.waitForURL((u) => u.origin === "http://127.0.0.1:9100");
  await expect(
    page.getByRole("heading", {
      name: "Synthetic FINLEAK identity provider",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByLabel("Username", { exact: true })
    .fill(required(`PRODUCT_${persona}_USERNAME`));
  await page
    .getByLabel("Password", { exact: true })
    .fill(required(`PRODUCT_${persona}_PASSWORD`));
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await page.waitForURL(
    (u) => u.origin === base && !u.pathname.startsWith("/api/auth/"),
  );
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Financial overview", exact: true }),
  ).toBeVisible();
}
async function call(context: BrowserContext, path: string, body?: unknown) {
  return body === undefined
    ? context.request.get(base + path)
    : context.request.post(base + path, {
        data: body,
        headers: {
          Origin: base,
          "Content-Type": "application/json",
          "Idempotency-Key": randomUUID(),
        },
      });
}
function leaves(value: unknown, prefix = ""): string[] {
  return value !== null && typeof value === "object"
    ? Object.entries(value).flatMap(([key, next]) =>
        leaves(next, `${prefix}/${key}`),
      )
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
    reason: "SYNTHETIC P0 explicit review",
    uncertainty_resolution:
      "Synthetic dates, units, tax basis and rounding reviewed; no scanner or extraction claim",
    evidence: [
      {
        document_id: document,
        location: "Synthetic source CSV, complete reviewed record",
        quote,
        field_id: null,
        manual: true,
        supports: leaves(value),
      },
    ],
  };
}
function witness(
  evaluation: string,
  decision: string,
  packageId: string,
  count: number,
) {
  const done = spawnSync(
    required("PRODUCT_PYTHON"),
    [
      "bench/p0/witness.py",
      "--evaluation",
      evaluation,
      "--decision",
      decision,
      "--package",
      packageId,
      "--count",
      String(count),
    ],
    { cwd: "..", env: process.env, encoding: "utf8", timeout: 10000 },
  );
  expect(done.status, "Independent PostgreSQL witness process").toBe(0);
  const value = JSON.parse(done.stdout);
  expect(value.status).toBe("PASS");
  return value;
}

test("OIDC browser login to reviewed financial decision, real PostgreSQL and restart", async ({
  browser,
}) => {
  const roster = JSON.parse(
    readFileSync("../.local/product-v11/roster.json", "utf8"),
  );
  expect(roster.synthetic).toBe(true);
  const owner = await browser.newContext({ baseURL: base });
  const analyst = await browser.newContext({ baseURL: base });
  const anonymous = await browser.newContext({ baseURL: base });
  const contexts = [owner, analyst, anonymous];
  // Browser requests are restricted to this disposable loopback bench.
  for (const context of contexts)
    await context.route("**/*", (route) => {
      const u = new URL(route.request().url());
      return ["127.0.0.1", "localhost"].includes(u.hostname)
        ? route.continue()
        : route.abort("blockedbyclient");
    });
  const page = await owner.newPage();
  const analystPage = await analyst.newPage();
  const root = `/api/organizations/${roster.organization}/financial`;
  try {
    expect((await call(anonymous, root + "/summary")).status()).toBe(401);
    expect(
      (
        await anonymous.request.get(
          `http://127.0.0.1:8000/api/v1/organizations/${roster.organization}/financial/summary`,
          {
            headers: { Authorization: "Bearer invalid-synthetic-token" },
          },
        )
      ).status(),
    ).toBe(401);
    await login(page, "OWNER");
    mark("owner_real_oidc_browser_session");
    await login(analystPage, "ANALYST");
    mark("analyst_real_oidc_browser_session");
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
      rationale: "SYNTHETIC P0 explicitly reviewed contract association",
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
      const revision = (await prepared.json()).id;
      expect(
        (
          await call(
            analyst,
            `${root}/sources/${source}/reviews`,
            review(kind, value, doc, roster.quotes[doc], "approved", revision),
          )
        ).status(),
      ).toBe(403);
      expect(
        (
          await call(
            owner,
            `${root}/sources/${source}/reviews`,
            review(kind, value, doc, roster.quotes[doc], "approved", revision),
          )
        ).status(),
      ).toBe(201);
    }
    mark("prepared_reviews_and_owner_approvals_through_existing_apis");
    const revisions = (
      await (await call(owner, `${root}/sources/${sources.invoice}`)).json()
    ).revision_ids;
    const evaluationResponse = await call(
      owner,
      `${root}/sources/${sources.invoice}/evaluate`,
      { scope_key: "line-1", expected_revisions: revisions },
    );
    expect(evaluationResponse.status()).toBe(200);
    const evaluated = await evaluationResponse.json();
    const detailResponse = await call(
      owner,
      `${root}/evaluations/${evaluated.id}`,
    );
    expect(detailResponse.status()).toBe(200);
    const evaluation = await detailResponse.json();
    expect([
      evaluation.expected,
      evaluation.actual,
      evaluation.potential,
      evaluation.currency,
    ]).toEqual(["5000.000000", "6000.000000", "1000.000000", "USD"]);
    mark("decimal_5000_6000_1000_USD");
    const provenance = evaluation.snapshot.inputs.flatMap(
      (r: { provenance: unknown[] }) => r.provenance,
    );
    expect(provenance.length).toBeGreaterThan(0);
    for (const item of provenance) {
      expect(Object.values(roster.documents)).toContain(item.document_id);
      expect(item.sha256).toMatch(/^[a-f0-9]{64}$/);
      expect(item.sha256).toBe(
        createHash("sha256")
          .update(roster.quotes[item.document_id])
          .digest("hex"),
      );
      expect(item.quote).toBe(roster.quotes[item.document_id]);
    }
    const proofRoot = `/api/organizations/${roster.organization}/proof`;
    const generated = await call(
      owner,
      `${proofRoot}/evaluations/${evaluation.id}/generate`,
      { mode: "CURRENT", expected_fingerprint: evaluation.fingerprint },
    );
    expect(generated.status()).toBe(200);
    const packageId = (await generated.json()).package_id;
    const proof = await (
      await call(owner, `${proofRoot}/packages/${packageId}`)
    ).json();
    expect(proof.core.sources.length).toBeGreaterThan(0);
    // The actual source gate must remain closed. No fabricated CLEAN/release records.
    expect(proof.core.completeness.state).toBe("INCOMPLETE");
    expect(
      proof.core.completeness.gaps.some(
        (g: { code: string }) => g.code === "C07",
      ),
    ).toBe(true);
    mark("citations_hashes_and_incomplete_unscanned_proof_preserved");
    const decisionPath = `${root}/evaluations/${evaluation.id}/decision`;
    const intent = {
      status: "confirmed",
      reason:
        "SYNTHETIC P0: reviewed USD 1000 discrepancy; sources remain unscanned",
      expected_decision: null,
    };
    expect((await call(analyst, decisionPath, intent)).status()).toBe(403);
    expect(
      (await call(owner, decisionPath, { ...intent, reason: "" })).status(),
    ).toBe(422);
    mark("analyst_decision_forbidden_and_empty_reason_rejected");
    await page.goto(`/invoices?org=${roster.organization}`);
    await expect(
      page.getByText("DEMO-ProductV11-invoice.csv", { exact: true }),
    ).toBeVisible();
    await page.goto(
      `/anomalies?org=${roster.organization}&assessment=${evaluation.id}`,
    );
    await expect(
      page
        .locator(".p-amount-strip")
        .getByText("1,000.00 USD", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("tab", { name: "Evidence & calculation", exact: true })
      .click();
    await expect(
      page.getByText("DEMO-ProductV11-contract.csv", { exact: true }).first(),
    ).toBeVisible();
    let submissions = 0;
    await page.route(`**${decisionPath}`, async (route) => {
      submissions += 1;
      const committed = await route.fetch();
      expect(committed.status()).toBe(201);
      // Real backend commit, deliberately lost response at the browser boundary.
      await route.abort("failed");
    });
    await page
      .getByLabel("Reason for decision", { exact: true })
      .fill(intent.reason);
    await page
      .getByRole("checkbox", {
        name: "I reviewed the source evidence and current assessment.",
        exact: true,
      })
      .check();
    await page
      .getByRole("button", { name: "Record financial decision", exact: true })
      .click();
    const recheck = page.getByRole("button", {
      name: "Reload current decision",
      exact: true,
    });
    await expect(recheck).toBeVisible();
    expect(submissions).toBe(1);
    await recheck.click();
    await expect(
      page.getByText(
        "Latest decision loaded. Review its audit entry before preparing a new decision. A changed ID alone does not establish who submitted it.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(submissions).toBe(1);
    await page.unroute(`**${decisionPath}`);
    mark("real_decision_commit_response_lost_then_get_no_automatic_retry");
    const persisted = await (
      await call(owner, `${root}/evaluations/${evaluation.id}`)
    ).json();
    expect(persisted.status).toBe("confirmed");
    witness(evaluation.id, persisted.decision_id, packageId, 1);
    expect((await call(owner, decisionPath, intent)).status()).toBe(409);
    await page.reload();
    await page
      .getByRole("tab", { name: "Review & audit history", exact: true })
      .click();
    await expect(page.getByText(intent.reason, { exact: true })).toBeVisible();
    const restarted = spawnSync(
      required("PRODUCT_PYTHON"),
      ["bench/p0/runtime.py", "restart-backend"],
      { cwd: "..", env: process.env, encoding: "utf8", timeout: 30000 },
    );
    expect(restarted.status).toBe(0);
    const fresh = await browser.newContext({ baseURL: base });
    contexts.push(fresh);
    await fresh.route("**/*", (route) => {
      const url = new URL(route.request().url());
      return ["127.0.0.1", "localhost"].includes(url.hostname)
        ? route.continue()
        : route.abort("blockedbyclient");
    });
    const freshPage = await fresh.newPage();
    await login(freshPage, "OWNER");
    const reread = await (
      await call(fresh, `${root}/evaluations/${evaluation.id}`)
    ).json();
    expect(reread.decision_id).toBe(persisted.decision_id);
    witness(evaluation.id, persisted.decision_id, packageId, 1);
    mark("new_oidc_session_and_independent_sql_after_backend_restart");
    const concurrent = await Promise.all([
      call(owner, decisionPath, {
        ...intent,
        status: "needs_review",
        expected_decision: persisted.decision_id,
      }),
      call(fresh, decisionPath, {
        ...intent,
        expected_decision: persisted.decision_id,
      }),
    ]);
    expect(concurrent.map((r) => r.status()).sort()).toEqual([201, 409]);
    mark("concurrent_201_and_409");
    const finalWitness = witness(
      evaluation.id,
      persisted.decision_id,
      packageId,
      2,
    );
    const history = await (
      await call(
        owner,
        `${root}/sources/${sources.contract}/history?limit=100&offset=0`,
      )
    ).json();
    const head = history.items.find(
      (r: { kind: string; state: string }) =>
        r.kind === "term" && r.state === "approved",
    );
    expect(
      (
        await call(
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
        )
      ).status(),
    ).toBe(201);
    const latest = await (
      await call(owner, `${root}/evaluations/${evaluation.id}`)
    ).json();
    expect(latest.stale).toBe(true);
    expect(
      (
        await call(owner, decisionPath, {
          ...intent,
          expected_decision: latest.decision_id,
        })
      ).status(),
    ).toBe(409);
    const packageHistory = await (
      await call(owner, `${proofRoot}/packages/${packageId}/history`)
    ).json();
    expect(
      packageHistory.items.some(
        (r: { kind: string }) => r.kind === "review.finalized",
      ),
    ).toBe(false);
    mark("stale_decision_rejected_and_proof_review_separate");
    writeFileSync(
      "../.local/p0-evidence/witness.json",
      JSON.stringify(
        {
          ...finalWitness,
          browser_version: browser.version(),
          backend_restart: "PASS",
          fresh_oidc_browser_session: "PASS",
          lost_response: "REAL_COMMIT_THEN_BROWSER_FAULT",
          automatic_decision_retries: 0,
          concurrent_http_statuses: [201, 409],
          stale_input: "REJECTED_409",
          proof_source_availability: "INCOMPLETE_UNSCANNED_GATE_PRESERVED",
          proof_review_separate: true,
          import: "NOT_TESTED",
          scanner: "BLOCKED",
          pitr_qualified: false,
        },
        null,
        2,
      ) + "\n",
    );
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});
