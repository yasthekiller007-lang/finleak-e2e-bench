import { randomUUID } from "node:crypto";
import { writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import {
  base,
  call,
  leaves,
  login,
  observations,
  observeOperations,
  origin,
  rawFields,
  roster,
  type Row,
} from "./helpers";

const contractBytes = Buffer.from(
  "field,value\nContract number,DEMO-C1\nSupplier,supplier-A\nCustomer,buyer-A\nCurrency,USD\nUnit price,10\nScope,SKU-A\n",
);
const invoiceBytes = Buffer.from(
  "field,value\nInvoice number,DEMO-I1\nSupplier,supplier-A\nCustomer,buyer-A\nInvoice date,2026-06-15\nCurrency,USD\nTotal,1200\nLine 1 description,Approved billed line\nLine 1 sku,SKU-A\nLine 1 quantity,100\nLine 1 unit price,12\nLine 1 unit,unit\nLine 1 total,1200\n",
);
const economicBytes = Buffer.from(
  "reference,principal,gross,net,tax,fees,withholding,status\nDEMO-CASH,60,60,60,0,0,0,settled\nDEMO-CREDIT,90,90,,0,0,0,issued\nDEMO-AP,40,40,,0,0,0,applied\nDEMO-RETURN,20,20,20,0,0,0,returned\n",
);

async function upload(
  page: Page,
  kind: string,
  name: string,
  bytes: Buffer,
  loseScan = false,
  expectQuota = false,
) {
  await page.goto("/documents");
  await page
    .getByLabel("File", { exact: true })
    .setInputFiles({ name, mimeType: "text/csv", buffer: bytes });
  await page.getByLabel("Document type").selectOption(kind);
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/documents") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Upload document", exact: true })
    .click();
  const uploaded = await response;
  expect(uploaded.status()).toBe(201);
  const doc = (await uploaded.json()) as Row;
  await expect(
    page.getByRole("status").filter({ hasText: "quarantined" }),
  ).toBeVisible();
  await page.getByRole("link", { name, exact: true }).click();
  await expect(page.getByText("Quarantined: not yet scanned")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Process document", exact: true }),
  ).toBeDisabled();
  const blocked = await page.request.get(`${base}/documents/${doc.id}/content`);
  expect(blocked.ok()).toBe(false);
  await page
    .getByLabel("Source action reason")
    .fill("DEMO exact original review");
  let firstScan = "";
  let firstKey = "";
  if (loseScan) {
    await page.route(`**/documents/${doc.id}/scan`, async (route) => {
      firstKey = route.request().headers()["idempotency-key"];
      const completed = await route.fetch();
      expect(completed.ok()).toBe(true);
      firstScan = (await completed.json()).scan_id;
      await route.abort("failed");
      await page.unroute(`**/documents/${doc.id}/scan`);
    });
  }
  await page.getByRole("button", { name: "Scan exact original" }).click();
  if (loseScan) {
    await expect(
      page
        .getByRole("region", { name: "Original availability" })
        .getByRole("alert"),
    ).toBeVisible();
    const retry = page.waitForRequest(
      (r) =>
        r.url().endsWith(`/documents/${doc.id}/scan`) && r.method() === "POST",
    );
    await page.getByRole("button", { name: "Scan exact original" }).click();
    expect((await retry).headers()["idempotency-key"]).toBe(firstKey);
  }
  await expect(
    page.getByText("Clean scan: awaiting owner/admin release"),
  ).toBeVisible();
  const clean = await call(page, `/documents/${doc.id}/source-status`);
  if (loseScan) expect(clean.scan_id).toBe(firstScan);
  const released = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/documents/${doc.id}/release`) &&
      r.request().method() === "POST",
  );
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Release clean original" }).click();
  const releaseResponse = await released;
  if (expectQuota) {
    expect(
      releaseResponse.status(),
      "Unchanged intake quota must reject attempt eleven",
    ).toBe(429);
    const retrySeconds = Number(releaseResponse.headers()["retry-after"]);
    expect(retrySeconds).toBe(60);
    expect((await releaseResponse.json()).error.code).toBe(
      "intake_actor_rate_limit",
    );
    await expect(
      page
        .getByRole("region", { name: "Original availability" })
        .getByRole("alert"),
    ).toBeVisible();
    expect((await call(page, `/documents/${doc.id}/source-status`)).state).toBe(
      "CLEAN_AWAITING_RELEASE",
    );
    expect(
      (await page.request.get(`${base}/documents/${doc.id}/content`)).ok(),
    ).toBe(false);
    expect((await page.request.get("/api/auth/session")).status()).toBe(200);
    expect(
      (await page.request.get("http://127.0.0.1:8000/api/v1/health")).status(),
    ).toBe(200);
    // Honor the actual server's bounded Retry-After, without changing quotas,
    // mutating clocks/counters or switching actor to evade the admission limit.
    await new Promise((resolve) => setTimeout(resolve, retrySeconds * 1000));
    await page.getByRole("button", { name: "Refresh availability" }).click();
    await expect(
      page.getByText("Clean scan: awaiting owner/admin release"),
    ).toBeVisible();
    const retryRelease = page.waitForResponse(
      (r) =>
        r.url().endsWith(`/documents/${doc.id}/release`) &&
        r.request().method() === "POST",
    );
    page.once("dialog", (dialog) => void dialog.accept());
    await page.getByRole("button", { name: "Release clean original" }).click();
    expect((await retryRelease).status()).toBe(200);
  } else
    expect(releaseResponse.status(), "Explicit clean-source release").toBe(200);
  await expect(
    page.getByRole("link", { name: "Download original", exact: true }),
  ).toBeVisible();
  const downloaded = await page.request.get(
    `${base}/documents/${doc.id}/content`,
  );
  expect(await downloaded.body()).toEqual(bytes);
  return doc;
}

test("E2E-02–09 coherent guarded source, review, proof, partial cash/credit, reversal and history", async ({
  page,
  browser,
}) => {
  test.setTimeout(180000);
  test
    .info()
    .annotations.push({ type: "browser", description: browser.version() });
  observations.length = 0;
  observeOperations(page);
  await login(page, "owner");
  const contract = await upload(
    page,
    "contract",
    "DEMO-contract.csv",
    contractBytes,
    true,
  );
  const invoice = await upload(
    page,
    "invoice",
    "DEMO-invoice.csv",
    invoiceBytes,
  );
  const processed = page.waitForResponse((r) =>
    r.url().endsWith(`/documents/${invoice.id}/process`),
  );
  await page
    .getByRole("button", { name: "Process document", exact: true })
    .click();
  expect((await processed).ok()).toBe(true);
  await expect(
    page.getByRole("button", { name: "Process again" }),
  ).toBeEnabled();
  const extraction = await call(page, `/documents/${invoice.id}/extraction`);
  expect(extraction.run).toBeTruthy();
  expect((await call(page, "/financial/evaluations")).total).toBe(0);
  const csource = await call(page, "/financial/sources", {
    document_id: contract.id,
    kind: "contract",
  });
  const isource = await call(page, "/financial/sources", {
    document_id: invoice.id,
    kind: "invoice",
  });
  const packet = {
    documents: [{ document_id: contract.id, role: "master" }],
    scopes: ["SKU-A"],
    effective_from: "2026-01-01",
    effective_to: null,
    open_ended: true,
    known_missing: [],
    complete: true,
    attestation: "DEMO governing packet reviewed",
    unresolved: [],
  };
  const association = {
    contract_source_id: csource.id,
    method: "manual",
    identifier: null,
    rationale: "DEMO exact obligation",
  };
  for (const [source, kind, value, doc] of [
    [csource, "term", roster.term, contract],
    [csource, "packet", packet, contract],
    [isource, "billing_scope", roster.billing, invoice],
    [isource, "association", association, invoice],
  ] as [Row, string, Record<string, unknown>, Row][]) {
    const review = await call(page, `/financial/sources/${source.id}/reviews`, {
      kind,
      key: value.key ?? kind,
      state: "prepared",
      expected_revision: null,
      reason: "DEMO explicit preparation",
      uncertainty_resolution: "DEMO cited source meaning reviewed",
      knowledge_cutoff: new Date().toISOString(),
      value,
      evidence: [
        {
          document_id: doc.id,
          location: "CSV row 2",
          quote: "DEMO explicit reviewed facts",
          field_id: null,
          manual: true,
          supports: leaves(value),
        },
      ],
    });
    expect(review.state).toBe("prepared");
    expect((await call(page, "/financial/evaluations")).total).toBe(0);
    await page.goto("/leakage-cases");
    await page
      .getByLabel("Reviewed source", { exact: true })
      .selectOption(source.id);
    const article = page
      .locator("article.financial-result")
      .filter({
        has: page.getByRole("heading", {
          name: `${kind.replaceAll("_", " ")} · ${value.key ?? kind}`,
          exact: true,
        }),
      })
      .last();
    await article
      .getByLabel("Decision reason", { exact: true })
      .fill("DEMO owner checked original and scope");
    await article.getByRole("checkbox").check();
    const approved = page.waitForResponse(
      (r) =>
        r.url().endsWith(`/sources/${source.id}/reviews`) &&
        r.request().method() === "POST",
    );
    await article
      .getByRole("button", { name: "Record authority decision" })
      .click();
    expect((await approved).status()).toBe(201);
    await expect(
      page.getByText(
        "Review action recorded. Reload current authority before continuing.",
      ),
    ).toBeVisible();
  }
  // The approval notice requires reloading current authority. Wait for the
  // fresh source snapshot before submitting its pinned revision set.
  await page.reload();
  await page
    .getByLabel("Reviewed source", { exact: true })
    .selectOption(isource.id);
  await page
    .getByLabel("Approved scope to assess")
    .selectOption(String(roster.billing.key));
  const evaluated = page.waitForResponse((r) =>
    r.url().endsWith(`/sources/${isource.id}/evaluate`),
  );
  await page.getByRole("button", { name: "Assess approved inputs" }).click();
  const evaluatedResponse = await evaluated;
  const assessment = (await evaluatedResponse.json()) as Row;
  expect(
    evaluatedResponse.status(),
    "Explicit current-input evaluation must succeed",
  ).toBe(200);
  expect(assessment.expected).toBe("1000.000000");
  expect(assessment.actual).toBe("1200.000000");
  expect(assessment.potential).toBe("200.000000");
  await page
    .getByRole("button", { name: "Review evidence", exact: true })
    .click();
  await expect(
    page.getByText(
      "Assessment loaded. No review or finding decision was changed.",
    ),
  ).toBeVisible();
  await page
    .getByLabel("Decision reason", { exact: true })
    .first()
    .fill("DEMO supported discrepancy confirmed");
  const confirmation = page.waitForResponse((r) =>
    r.url().endsWith(`/evaluations/${assessment.id}/decision`),
  );
  await page.getByRole("button", { name: "Save finding review" }).click();
  const decision = (await (await confirmation).json()) as Row;
  await expect(
    page.getByText(
      "Finding decision recorded. Historical calculated amounts are unchanged.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "View proof", exact: true }).click();
  const generated = page.waitForResponse((r) =>
    r.url().endsWith(`/evaluations/${assessment.id}/generate`),
  );
  const proofLoaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new RegExp(`/proof/packages/[0-9a-f-]{36}$`).test(
        new URL(r.url()).pathname,
      ),
  );
  await page
    .getByRole("button", { name: "Generate proof", exact: true })
    .click();
  const generationResponse = await generated;
  expect(generationResponse.ok(), "Explicit proof issuance").toBe(true);
  const proofId = String((await generationResponse.json()).package_id);
  // Inspect the package returned to the actual UI, rather than racing an extra
  // read against its bounded concurrent refresh/detail/history operations.
  const proofResponse = await proofLoaded;
  expect(new URL(proofResponse.url()).pathname).toBe(
    `${base}/proof/packages/${proofId}`,
  );
  expect(proofResponse.status()).toBe(200);
  const proof = (await proofResponse.json()) as Row;
  expect(proof.issued_completeness).toBe("COMPLETE");
  const requirements = (
    proof.core as {
      completeness: { requirements: Record<string, { passed: boolean }> };
    }
  ).completeness.requirements;
  expect(Object.keys(requirements).sort()).toEqual(
    Array.from({ length: 10 }, (_, i) => `C${String(i + 1).padStart(2, "0")}`),
  );
  expect(Object.values(requirements).every((v) => v.passed)).toBe(true);
  expect((await call(page, "/financial/evaluations")).total).toBe(1);
  const economic = await upload(
    page,
    "invoice",
    "DEMO-economic-evidence.csv",
    economicBytes,
    false,
    true,
  );
  await page.goto("/recovery-ledger");
  await page
    .getByLabel("Positive financial finding")
    .selectOption(String(assessment.id));
  const opened = page.waitForResponse(
    (r) =>
      r.url().endsWith("/recovery/cases") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Open investigation" }).click();
  const openedResponse = await opened;
  expect(openedResponse.status(), "Explicit recovery case identity").toBe(200);
  const recovery = (await openedResponse.json()) as Row;
  await expect(
    page.getByRole("button", { name: new RegExp(recovery.id.slice(0, 8)) }),
  ).toBeVisible();
  // This view appears after the current case/detail/history/proposal reads
  // complete. A journey-wide request set can retain requests from replaced
  // documents; use the actual current UI state before the next explicit read.
  await expect(
    page.getByRole("heading", { name: "Case evidence and authority" }),
  ).toBeVisible();
  const initialCase = await call(page, `/recovery/cases/${recovery.id}`);
  expect(initialCase.realized).toBe("0");
  expect(initialCase.claimed).toBeNull();
  expect(initialCase.acknowledged).toBeNull();

  async function approve(value: Record<string, unknown>) {
    const state = await call(page, `/recovery/cases/${recovery.id}`);
    const proposalId = randomUUID();
    const material = rawFields(value);
    const proposal = await call(
      page,
      `/recovery/cases/${recovery.id}/proposals`,
      {
        value,
        expected_head: state.head_id,
        reason: `DEMO proposal ${proposalId}`,
        evidence: [
          {
            document_id: economic.id,
            locator: "DEMO CSV transaction rows 2–5",
            quotation: "DEMO independently reviewed economic evidence",
            supports: Object.keys(material),
            raw_fields: material,
            reviewed_fields: material,
          },
        ],
      },
    );
    // Replace unique locator reason with actual proposal id for robust visible selection.
    await page.goto("/recovery-ledger");
    await page
      .getByRole("button", { name: new RegExp(recovery.id.slice(0, 8)) })
      .click();
    await page
      .getByLabel("Action / approval reason")
      .fill("DEMO exact economic evidence reviewed");
    const target = page
      .locator("article")
      .filter({ hasText: `DEMO proposal ${proposalId}` });
    const result = page.waitForResponse((r) =>
      r.url().endsWith(`/proposals/${proposal.id}/decision`),
    );
    await target
      .getByRole("button", { name: "Approve exact proposal" })
      .click();
    const response = await result;
    expect(
      response.ok(),
      `Safe economic approval status ${response.status()}`,
    ).toBe(true);
    await expect(
      page.getByText("Reviewed authority recorded; inspect current measures."),
    ).toBeVisible();
    await expect(
      target.getByRole("button", { name: "Approve exact proposal" }),
    ).toBeDisabled();
    return (await response.json()) as Row;
  }
  const parties = {
    payer: "supplier-A",
    payee: "buyer-A",
    beneficiary: "buyer-A",
  };
  const party = await approve({
    kind: "party",
    supplier: "supplier-A",
    customer: "buyer-A",
    ...parties,
    valid_from: "2026-01-01",
    valid_to: null,
    relationship: "DIRECT",
    discharge: "DEMO vendor obligation discharged to customer",
  });
  const readiness = await approve({
    kind: "readiness",
    proof_id: proofId,
    decision_id: decision.id,
    party_id: party.id,
    pursuit: "150",
    quantum: "0.01",
    currency: "USD",
    tax_basis: "EXCLUSIVE",
    scope: "SKU-A",
    reconciliation: "COMPLETE",
  });
  async function instrument(kind: string, amount: string) {
    const identity = await call(page, "/recovery/instruments", {
      kind,
      namespace: "DEMO/synthetic",
      issuer: "supplier-A",
      reference: randomUUID(),
      currency: "USD",
    });
    const reviewed = await approve({
      kind: "instrument",
      instrument_id: identity.id,
      principal: amount,
      gross: amount,
      tax: "0",
      other: "0",
      tax_basis: "EXCLUSIVE",
      tax_recoverability: "NOT_ASSESSED",
      reconciliation: "COMPLETE",
      economic: { precision: "DATE", day: "2026-10-01" },
      ...parties,
      scope: "SKU-A",
      related_cases: [recovery.id],
      origin: "POST_FINDING_REMEDY",
      status: kind === "CREDIT" ? "ISSUED" : "SETTLED",
    });
    return [identity, reviewed];
  }
  function allocation(
    identity: Row,
    reviewed: Row,
    amount: string,
    method = "CASH",
  ) {
    return {
      kind: "realization",
      instrument_id: identity.id,
      instrument_review_id: reviewed.id,
      party_id: party.id,
      readiness_id: readiness.id,
      method,
      economic: { precision: "DATE", day: "2026-10-01" },
      amount,
      principal: amount,
      gross: amount,
      tax: "0",
      fees: "0",
      withholding: "0",
      net_cash: method === "CASH" ? amount : null,
      other: "0",
      tax_basis: "EXCLUSIVE",
      tax_recoverability: "NOT_ASSESSED",
      reconciliation: "COMPLETE",
      currency: "USD",
      quantum: "0.01",
      event_reference: randomUUID(),
      ...parties,
      scope: "SKU-A",
      completed: true,
      discharge: "DEMO actual supported completed performance",
      ...(method === "APPLIED_CREDIT"
        ? { application_reference: "DEMO-AP-40" }
        : {}),
    };
  }
  const [cash, cashReview] = await instrument("CASH", "60");
  const receipt = await approve(allocation(cash, cashReview, "60"));
  const [credit, creditReview] = await instrument("CREDIT", "90");
  let state = await call(page, `/recovery/cases/${recovery.id}`);
  expect(state.realized).toBe("60.000000");
  expect(state.pending_credit).toBe("90.000000");
  await approve(allocation(credit, creditReview, "40", "APPLIED_CREDIT"));
  state = await call(page, `/recovery/cases/${recovery.id}`);
  expect(state.realized).toBe("100.000000");
  expect(state.net_cash).toBe("60.000000");
  expect(state.pending_credit).toBe("50.000000");
  await call(page, `/recovery/cases/${recovery.id}/inspect`, {
    expected_head: state.head_id,
    reason: "DEMO historical authority observation",
  });
  const reportBody = {
    known_at: new Date().toISOString(),
    start: { precision: "DATE", day: "2026-01-01" },
    end: { precision: "DATE", day: "2027-01-01" },
    currency: "USD",
    customer: "buyer-A",
    tax_basis: "EXCLUSIVE",
  };
  const prior = await call(page, "/recovery/report", reportBody);
  await approve({
    kind: "reversal",
    original_id: receipt.id,
    amount: "20",
    reversal_type: "ECONOMIC_RETURN",
    cash_return: "20",
    economic: { precision: "DATE", day: "2026-10-02" },
    event_reference: "DEMO-return-20",
    discharge: "DEMO actual cash returned",
  });
  state = await call(page, `/recovery/cases/${recovery.id}`);
  expect(state.realized).toBe("80.000000");
  expect(state.net_cash).toBe("40.000000");
  expect((await call(page, "/recovery/report", reportBody)).digest).toBe(
    prior.digest,
  );
  expect((await call(page, `/proof/packages/${proofId}`)).fingerprint).toBe(
    proof.fingerprint,
  );
  const forged = await page.request.post(`${base}/recovery/cases`, {
    headers: { Origin: "https://forged.invalid" },
    data: { evaluation_id: assessment.id },
  });
  expect(forged.status()).toBe(403);
  const negative = await page.request.get(
    `/api/organizations/${roster.other}/documents/${invoice.id}`,
  );
  expect(negative.status()).toBe(404);
  // Four actual parallel requests, through the same cookie/proxy and independent API workers.
  await Promise.all(
    Array.from({ length: 4 }, () =>
      call(
        page,
        "/financial/summary",
        undefined,
        randomUUID(),
        "parallel_summary",
      ),
    ),
  );
  await page.reload();
  await page
    .getByRole("button", { name: new RegExp(recovery.id.slice(0, 8)) })
    .click();
  const money = page
    .locator("dl > div")
    .filter({ has: page.getByText("Actual net bank cash N", { exact: true }) });
  await expect(money).toContainText("USD 40.000000");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(
    (
      await page.request.get(`${base}/documents/${invoice.id}/content`)
    ).status(),
  ).toBe(401);
  const grouped = Object.groupBy(observations, (v) =>
    v.operation.includes("/reviews")
      ? "review"
      : v.operation.includes("/report")
        ? "report"
        : v.operation.includes("/generate")
          ? "proof"
          : v.operation.includes("/cases/")
            ? "recovery_read_or_prepare"
            : v.operation,
  );
  const latencies = Object.fromEntries(
    Object.entries(grouped).map(([operation, samples]) => {
      const sorted = samples!.map((s) => s.latency_ms).sort((a, b) => a - b);
      return [
        operation,
        {
          n: sorted.length,
          p50_ms: sorted[Math.ceil(sorted.length * 0.5) - 1],
          p95_ms: sorted[Math.ceil(sorted.length * 0.95) - 1],
          max_ms: sorted.at(-1),
          statuses: samples!.map((s) => s.status),
        },
      ];
    }),
  );
  writeFileSync(
    "../.local/phase7/capacity.json",
    JSON.stringify(
      {
        release_sha: process.env.RELEASE_SHA,
        date: new Date().toISOString(),
        tester: "Playwright synthetic journey",
        browser: browser.version(),
        schema: "0009",
        profiles: [
          "pilot-intake/1",
          "proof-operations/1",
          "recovery-operations/1",
          "linux-parser/1",
        ],
        dataset: {
          companies: 1,
          negative_tenants: 1,
          identities: 6,
          originals: 3,
          bytes:
            contractBytes.length + invoiceBytes.length + economicBytes.length,
          evaluations: 1,
          proofs: 1,
          api_workers: 2,
          parallel_reads: 4,
        },
        admission: {
          actor_attempts_per_minute: 10,
          attempt_eleven_status: 429,
          retry_after_seconds: 60,
          after_window_release_status: 200,
        },
        latency_scope:
          "Browser request-finished timings for UI commands plus protected proxy API request timings; UI interaction/review time is excluded",
        latencies,
        verdict: "OBSERVED_SYNTHETIC_ENVELOPE_ONLY",
        limits:
          "No enrolled customer extremes, approved latency target, cloud IO, production image, sustained-write load or manual acceptance qualification",
      },
      null,
      2,
    ),
  );
});

for (const role of ["owner", "admin", "analyst", "viewer"]) {
  test(`E2E-06 ${role} role visibility and independent server denial`, async ({
    page,
  }) => {
    await login(page, role);
    if (role === "viewer") {
      await expect(
        page.getByRole("button", { name: "Upload document" }),
      ).toHaveCount(0);
      const forbidden = await page.request.post(base + "/financial/sources", {
        headers: { Origin: origin },
        data: { document_id: randomUUID(), kind: "invoice" },
      });
      expect(forbidden.status()).toBe(403);
    } else
      await expect(
        page.getByRole("button", { name: "Upload document" }),
      ).toBeVisible();
    const denied = await page.request.get(
      `/api/organizations/${roster.other}/documents`,
    );
    expect(denied.status()).toBe(404);
    const assessments = await call(page, "/financial/evaluations");
    const finding = (assessments.items as Row[])[0];
    expect(
      finding,
      "Coherent journey must produce the review fixture",
    ).toBeTruthy();
    await page.goto("/leakage-cases");
    await page
      .getByRole("button", { name: "Review evidence", exact: true })
      .click();
    await expect(
      page.getByText(
        "Assessment loaded. No review or finding decision was changed.",
      ),
    ).toBeVisible();
    if (role === "owner" || role === "admin") {
      await expect(
        page.getByRole("button", { name: "Save finding review" }),
      ).toBeVisible();
    } else {
      await expect(
        page.getByRole("button", { name: "Save finding review" }),
      ).toHaveCount(0);
      const forbidden = await page.request.post(
        `${base}/financial/evaluations/${finding.id}/decision`,
        {
          headers: { Origin: origin },
          data: {
            status: "confirmed",
            expected_decision: finding.decision_id,
            reason: "DEMO final-authority denial",
          },
        },
      );
      expect(forbidden.status()).toBe(403);
    }
  });
}

test("E2E-01/10 no membership, keyboard controls and forged browser bearer", async ({
  page,
}) => {
  await login(page, "unassigned");
  await expect(
    page.getByRole("heading", { name: "No organization access yet" }),
  ).toBeVisible();
  expect((await page.request.get(base + "/documents")).status()).toBe(404);
  const signOut = page.getByRole("button", { name: "Sign out" });
  await expect(signOut).toBeEnabled();
  await signOut.focus();
  await expect(signOut).toBeFocused();
  await signOut.press("Enter");
  await expect(page).toHaveURL(/\/login$/);
  const forged = await page.request.get(base + "/documents", {
    headers: { Authorization: "Bearer browser-forgery" },
  });
  expect(forged.status()).toBe(401);
});

test("FAIL-04 / AC7-35 history outage removes stale monetary view and controls", async ({
  page,
}) => {
  await login(page, "owner");
  const cases = await call(page, "/recovery/cases");
  const recovery = (cases.items as Row[])[0];
  expect(recovery).toBeTruthy();
  await page.goto("/recovery-ledger");
  await page
    .getByRole("button", { name: new RegExp(recovery.id.slice(0, 8)) })
    .click();
  await expect(
    page.getByText("Actual net bank cash N", { exact: true }),
  ).toBeVisible();
  const before = await call(page, `/recovery/cases/${recovery.id}`);
  await page.route(`**/recovery/cases/${recovery.id}/history?**`, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { message: "Synthetic history outage" } }),
    }),
  );
  await page
    .getByLabel("Action / approval reason")
    .fill("DEMO fault-path observation");
  const inspected = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/recovery/cases/${recovery.id}/inspect`) &&
      r.request().method() === "POST",
  );
  const historyFailed = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname.endsWith(
        `/recovery/cases/${recovery.id}/history`,
      ) && r.status() === 503,
  );
  await page
    .getByRole("button", { name: "Record current readiness inspection" })
    .click();
  expect(
    (await inspected).status(),
    "Explicit inspection before reload fault",
  ).toBe(200);
  expect((await historyFailed).status()).toBe(503);
  await expect(
    page.getByRole("alert").filter({ hasText: "Synthetic history outage" }),
  ).toContainText("Synthetic history outage");
  await expect(
    page.getByText("Actual net bank cash N", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Approve exact proposal" }),
  ).toHaveCount(0);
  const after = await call(page, `/recovery/cases/${recovery.id}`);
  expect(after.realized).toBe(before.realized);
  expect(after.net_cash).toBe(before.net_cash);
});
