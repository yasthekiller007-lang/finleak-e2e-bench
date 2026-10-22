/** Pure public-criteria contract tests. No authenticated runtime is simulated. */
import { describe, expect, it } from "vitest";
import {
  absoluteViewLink,
  readViewSearch,
  searchFromRecord,
  viewDefaults,
  viewPath,
} from "@/lib/exception-view-url";
const org = "00000000-0000-4000-8000-000000000002";
const id = "abcdefab-abcd-abcd-abcd-abcdefabcdef";
const parse = (query: string) => readViewSearch(query, "anomalies", false);
const link = (query: string) => `?ev=1&org=${org}${query ? "&" + query : ""}`;
it("round trips the complete whitelist deterministically, with exact supplier strings and Unicode", () => {
  const filters = {
    q: "Écart 東京 & %_",
    supplier: " Société A & B ",
    invoice_source_id: id.toUpperCase(),
    invoice_document_id: org,
    contract_source_id: id,
    currency: "USD",
    outcome: "POTENTIAL_LEAKAGE",
    decision_status: "unrecorded",
    created_from: "2026-10-01T01:00:00+01:00",
    created_to: "2026-11-01T00:00:00Z",
    current: true,
    needs_review: true,
    sort: "amount_high",
  };
  const path = viewPath(org, filters, 50, "anomalies", false);
  const restored = parse(path.slice(path.indexOf("?")));
  expect(restored).toMatchObject({
    org,
    limit: 50,
    versioned: true,
    assessment: "",
    filters: {
      ...filters,
      invoice_source_id: id,
      created_from: "2026-10-01T00:00:00.000Z",
      created_to: "2026-11-01T00:00:00.000Z",
    },
  });
  expect(viewPath(org, { ...restored.filters }, 50, "anomalies", false)).toBe(
    path,
  );
  expect(
    viewPath(
      org,
      Object.fromEntries(Object.entries(restored.filters).reverse()),
      50,
      "anomalies",
      false,
    ),
  ).toBe(path);
});
it("keeps coherent defaults and can explicitly disable the review default", () => {
  expect(parse("")).toMatchObject({
    org: "",
    filters: viewDefaults("anomalies"),
    limit: 20,
  });
  expect(readViewSearch("", "review", true)).toMatchObject({
    filters: { needs_review: true, sort: "newest" },
    limit: 2,
  });
  const path = viewPath(org, { needs_review: false }, 20, "review", false);
  expect(path).toContain("ev_needs_review=false");
  expect(
    readViewSearch(path.split("?")[1], "review", false).filters.needs_review,
  ).toBe(false);
});
it("retains legacy organization/invoice/assessment links, without copying the investigation", () => {
  expect(parse(`?org=${org}&invoice=${id}&assessment=${id}`)).toMatchObject({
    org,
    assessment: id,
    filters: { invoice_source_id: id },
    versioned: false,
  });
  expect(
    viewPath(
      org,
      parse(`?invoice=${id}&assessment=${id}`).filters,
      20,
      "anomalies",
      false,
    ),
  ).not.toContain("assessment");
  expect(
    searchFromRecord({ org, invoice: [id, id], empty: undefined }),
  ).toContain(`invoice=${id}&invoice=${id}`);
  expect(() => parse(searchFromRecord({ org: [org, org] }))).toThrow();
});
it("serializes only allowed criteria, never cursors, financial data or authorization", () => {
  const path = viewPath(
    org,
    {
      q: "public",
      after: "SECRET",
      token: "SECRET",
      reason: "SECRET",
      citation: "SECRET",
      potential: "999",
    } as never,
    20,
    "anomalies",
    false,
  );
  expect(path).not.toMatch(/SECRET|after|token|reason|citation|potential/);
  expect(absoluteViewLink("https://cloud.example", path)).toBe(
    "https://cloud.example" + path,
  );
  expect(viewPath(org, {}, 2, "anomalies", true)).toMatch(
    /^\/demo\/anomalies\?/,
  );
  expect(() => parse(link("ev_limit=2"))).toThrow();
});
describe("rejects malformed or widening criteria before reads", () => {
  it.each([
    "ev=2",
    "ev=01",
    `org=${org}&org=${org}`,
    "unknown=1",
    "after=opaque",
    "token=secret",
    "ev_currency=usd",
    "ev_currency=US",
    "ev_sort=surprise",
    "ev_outcome=CONFIRMED",
    "ev_decision_status=owner",
    "ev_current=1",
    "ev_needs_review=TRUE",
    "ev_missing_contract=",
    "ev_limit=200",
    "ev_limit=020",
    "ev_q=",
    "ev_q=%FF",
    "ev_q=%ZZ",
    "ev_q=%00",
    "ev_q=x&&ev_supplier=a",
    "ev_q=x&",
    "ev_q",
    "ev_invoice_source_id=invalid",
    "ev_invoice_document_id=invalid",
    "ev_contract_source_id=invalid",
    `ev_missing_contract=true&ev_contract_source_id=${id}`,
    `invoice=${id}`,
    "ev_created_from=2026-02-30T00%3A00%3A00Z",
    "ev_created_from=2026-10-01T24%3A00%3A00Z",
    "ev_created_from=0000-01-01T00%3A00%3A00Z",
    "ev_created_from=2026-10-02T00%3A00%3A00Z&ev_created_to=2026-10-01T00%3A00%3A00Z",
  ])("rejects %s", (value) => expect(() => parse(link(value))).toThrow());
  it.each([
    "?ev=1",
    `?org=${org}&ev_q=test`,
    "?org=",
    `?org=${org}&assessment=bad`,
    "?" + "q".repeat(4097),
  ])(
    "rejects missing scope/version, invalid legacy ID or oversized URL %s",
    (s) => expect(() => parse(s)).toThrow(),
  );
  it("bounds Unicode, text lengths and complete origin+path", () => {
    expect(() =>
      viewPath(org, { q: "x".repeat(161) }, 20, "anomalies", false),
    ).toThrow();
    expect(() =>
      viewPath(org, { supplier: "x".repeat(121) }, 20, "anomalies", false),
    ).toThrow();
    expect(() =>
      viewPath(org, { q: "\ud800" }, 20, "anomalies", false),
    ).toThrow();
    const path = viewPath(
      org,
      { q: "界".repeat(160), supplier: "界".repeat(120) },
      20,
      "anomalies",
      false,
    );
    expect(() =>
      absoluteViewLink("https://" + "x".repeat(2000) + ".example", path),
    ).toThrow();
  });
  it.each([
    "https://outside.test/anomalies",
    "https://cloud.example/anomalies",
    "//cloud.example/anomalies",
    "/invoices",
    "/anomalies#secret",
    "/anomalies?token=bad",
  ])("rejects noncanonical/untrusted link target %s", (path) =>
    expect(() => absoluteViewLink("https://cloud.example", path)).toThrow(),
  );
});
