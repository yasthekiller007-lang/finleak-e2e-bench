/** Controlled API-boundary fixtures. No live OIDC/PostgreSQL claim. */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductConsole } from "@/components/product-console";
import { ExceptionInvestigation } from "@/components/exception-investigation";
import { ExceptionPortfolio } from "@/components/exception-portfolio";
import {
  compareDecimal,
  contractName,
  hasNextWindow,
  mergeRecords,
  portfolio,
  queueRows,
  type QueueFilters,
} from "@/lib/exception-workbench";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import {
  liveWorkspaceGateway,
  type WorkspaceData,
} from "@/lib/product-workspace";
const org = demoUser.organizations[0].id;
const signal = () => new AbortController().signal;
const defaults: QueueFilters = {
  search: "",
  status: "all",
  currency: "all",
  supplier: "all",
  contract: "all",
  sort: "newest",
  invoice: "",
  reviewOnly: false,
};
const fixture = () => withSyntheticExceptionContext(createDemoGateway());

describe("exact recorded-value queue operations", () => {
  it.each([
    ["9007199254740992.000001", "9007199254740992.000002", -1],
    ["1.000000", "1", 0],
    ["-1.000001", "-1", -1],
    ["0.00000001", "0.000000009", 1],
  ])("compares %s and %s without floating-point loss", (a, b, expected) =>
    expect(compareDecimal(a, b)).toBe(expected),
  );
  it("rejects exponential or invalid recorded numbers", () => {
    expect(() => compareDecimal("1e6", "1")).toThrow();
  });
  it("groups currencies before exact amount ordering and keeps unknown amounts last within a currency", async () => {
    const data = await fixture().load(org, signal()),
      base = data.assessments.items[0];
    data.assessments.items = [
      { ...base, id: "USD-low", potential: "9007199254740992.000001" },
      { ...base, id: "USD-high", potential: "9007199254740992.000002" },
      { ...base, id: "EUR", currency: "EUR", potential: "1" },
      { ...base, id: "USD-unknown", potential: null },
    ];
    expect(
      queueRows(data, { ...defaults, sort: "amount_high" }).map((a) => a.id),
    ).toEqual(["EUR", "USD-high", "USD-low", "USD-unknown"]);
    expect(
      queueRows(data, { ...defaults, currency: "USD", sort: "amount_low" }).map(
        (a) => a.id,
      ),
    ).toEqual(["USD-low", "USD-high", "USD-unknown"]);
  });
  it("never ranks monetary values of unspecified currencies", async () => {
    const data = await fixture().load(org, signal()),
      base = data.assessments.items[0];
    data.assessments.items = [
      {
        ...base,
        id: "older-large",
        currency: null,
        potential: "9999",
        created_at: "2026-10-10T00:00:00Z",
      },
      {
        ...base,
        id: "newer-small",
        currency: null,
        potential: "1",
        created_at: "2026-10-11T00:00:00Z",
      },
    ];
    expect(
      queueRows(data, { ...defaults, sort: "amount_high" }).map((a) => a.id),
    ).toEqual(["newer-small", "older-large"]);
  });
  it("combines supplier, contract, currency and search from returned references", async () => {
    const data = await fixture().load(org, signal()),
      a = data.assessments.items[0];
    expect(
      queueRows(data, {
        ...defaults,
        currency: "USD",
        supplier: JSON.stringify("AcmeCloud"),
        contract: JSON.stringify(a.queue_context!.contract_source_id),
        search: "MASTER-SERVICES",
      }).map((a) => a.id),
    ).toEqual([a.id]);
    expect(
      queueRows(data, { ...defaults, supplier: JSON.stringify("unavailable") })
        .length,
    ).toBe(0);
  });
  it("retains missing references and stale rows explicitly without making them actionable", async () => {
    const data = await fixture().load(org, signal()),
      base = data.assessments.items[0];
    data.assessments.items = [
      { ...base, stale: true, status: "confirmed", queue_context: undefined },
    ];
    expect(
      queueRows(data, { ...defaults, supplier: "null", contract: "null" }),
    ).toHaveLength(1);
    expect(queueRows(data, { ...defaults, reviewOnly: true })).toHaveLength(0);
    expect(
      queueRows(data, { ...defaults, status: "Reassessment needed" }),
    ).toHaveLength(1);
    expect(contractName(data, "unloaded-id")).toBe(
      "Contract source unloaded-id",
    );
  });
  it("orders statuses and dates while preserving an invoice source restriction", async () => {
    const data = await fixture().load(org, signal());
    const rows = queueRows(data, { ...defaults, sort: "oldest" });
    expect(rows[0].created_at <= rows.at(-1)!.created_at).toBe(true);
    expect(
      queueRows(data, {
        ...defaults,
        invoice: rows[0].invoice_source_id,
      }).every((a) => a.invoice_source_id === rows[0].invoice_source_id),
    ).toBe(true);
    const labels = queueRows(data, { ...defaults, sort: "status" }).map(
      (a) => a.status,
    );
    expect(labels).toHaveLength(data.assessments.items.length);
  });
  it("deduplicates overlapping pages by ID and uses server windows to terminate pagination", () => {
    expect(
      mergeRecords(
        [{ id: "a", value: 1 }],
        [
          { id: "a", value: 2 },
          { id: "b", value: 3 },
        ],
      ),
    ).toEqual([
      { id: "a", value: 2 },
      { id: "b", value: 3 },
    ]);
    expect(hasNextWindow({ offset: 0, limit: 100, total: 101 })).toBe(true);
    expect(hasNextWindow({ offset: 100, limit: 100, total: 101 })).toBe(false);
  });
  it("reports counts separately from authoritative backend monetary totals", async () => {
    const data = await fixture().load(org, signal()),
      original = structuredClone(data.summary);
    const result = portfolio(data);
    expect(result.currencies.map(([currency]) => currency)).toEqual([
      "EUR",
      "USD",
    ]);
    expect(result.currencies.reduce((n, [, r]) => n + r.count, 0)).toBe(
      data.assessments.items.length,
    );
    expect(data.summary).toEqual(original);
    expect(result.currencies.every(([, row]) => !("amount" in row))).toBe(true);
  });
});

describe("interactive workbench with explicit synthetic gateway", () => {
  it("filters, clears an empty result, and navigates to the recorded investigation", async () => {
    render(
      <ProductConsole
        user={demoUser}
        view="anomalies"
        gateway={fixture()}
        demo
      />,
    );
    await screen.findByRole("heading", { name: "Financial exceptions queue" });
    fireEvent.change(screen.getByLabelText("Supplier filter"), {
      target: { value: JSON.stringify("AcmeCloud") },
    });
    fireEvent.change(screen.getByLabelText("Currency filter"), {
      target: { value: "EUR" },
    });
    expect(screen.getByText("No matching assessments")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));
    fireEvent.click(
      screen.getByRole("button", {
        name: "Review evidence for Enterprise seats · October",
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Trace the exception to its basis",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Document: AcmeCloud_Master-Services-2026.pdf"),
    ).toBeInTheDocument();
    expect(screen.getByText("26,880.00 USD")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Direct case link" }),
    ).toHaveAttribute(
      "href",
      `/demo/anomalies?org=${org}&assessment=00000000-0000-4000-8000-000000001001`,
    );
    expect(
      screen.getByRole("button", { name: "Save demo decision" }),
    ).toBeDisabled();
  });
  it("paginates a loaded register and resets to page one when filters change", async () => {
    const gateway = fixture(),
      read = gateway.load;
    gateway.load = async (...args) => {
      const data = await read(...args);
      return {
        ...data,
        assessments: {
          ...data.assessments,
          total: 23,
          items: Array.from({ length: 23 }, (_, i) => ({
            ...data.assessments.items[0],
            id: `synthetic-${i}`,
            scope_summary: {
              ...data.assessments.items[0].scope_summary!,
              label: `Synthetic row ${i}`,
            },
          })),
        },
      };
    };
    render(
      <ProductConsole user={demoUser} view="anomalies" gateway={gateway} />,
    );
    const nav = await screen.findByRole("navigation", {
      name: "Exception queue pagination",
    });
    expect(nav).toHaveTextContent("Page 1 of 3");
    fireEvent.click(within(nav).getByRole("button", { name: "Next page" }));
    expect(nav).toHaveTextContent("Page 2 of 3");
    fireEvent.change(screen.getByLabelText("Search loaded records"), {
      target: { value: "row 22" },
    });
    expect(
      screen.getByRole("button", {
        name: "Review evidence for Synthetic row 22",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "Exception queue pagination" }),
    ).not.toBeInTheDocument();
  });
  it("shows pagination errors without discarding existing rows and permits an explicit retry", async () => {
    const gateway = fixture(),
      read = gateway.load;
    gateway.load = async (...args) => {
      const data = await read(...args);
      return { ...data, assessments: { ...data.assessments, total: 101 } };
    };
    gateway.assessments = vi
      .fn()
      .mockRejectedValueOnce(new Error("Synthetic page unavailable"))
      .mockImplementation(async () => ({
        items: [],
        total: 101,
        offset: 100,
        limit: 100,
      }));
    render(
      <ProductConsole user={demoUser} view="anomalies" gateway={gateway} />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Load more records" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Synthetic page unavailable",
    );
    expect(
      screen.getByRole("button", {
        name: "Review evidence for Enterprise seats · October",
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Load more records" }));
    await screen.findByText(/4 \/ 101 loaded/);
    expect(gateway.assessments).toHaveBeenCalledTimes(2);
  });
  it("loads source references from the existing tenant-scoped API without a bearer header", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        Response.json({ items: [], total: 100, limit: 100, offset: 100 }),
      );
    try {
      await liveWorkspaceGateway.sources!(org, 100, signal());
      expect(fetcher).toHaveBeenCalledWith(
        `/api/organizations/${org}/financial/sources?limit=100&offset=100`,
        expect.objectContaining({ credentials: "same-origin", method: "GET" }),
      );
      expect(fetcher.mock.calls[0][1]?.headers).toBeUndefined();
    } finally {
      fetcher.mockRestore();
    }
  });
  it("does not disclose a late source page after changing organizations", async () => {
    const gateway = fixture(),
      read = gateway.load,
      initial = await read(org, signal());
    const other = "00000000-0000-4000-8000-000000000003";
    let resolve!: (page: WorkspaceData["sources"]) => void,
      oldSignal!: AbortSignal;
    gateway.load = async (id, sig) =>
      id === org
        ? {
            ...(await read(id, sig)),
            sources: { ...initial.sources, total: 101 },
          }
        : {
            ...initial,
            sources: { items: [], total: 0, limit: 100, offset: 0 },
            documents: { items: [], total: 0, limit: 100, offset: 0 },
            assessments: { items: [], total: 0, limit: 100, offset: 0 },
          };
    gateway.sources = vi.fn((_id, _offset, sig) => {
      oldSignal = sig;
      return new Promise<WorkspaceData["sources"]>((r) => {
        resolve = r;
      });
    });
    render(
      <ProductConsole
        user={{
          ...demoUser,
          organizations: [
            ...demoUser.organizations,
            { id: other, name: "Other synthetic organization", role: "viewer" },
          ],
        }}
        view="anomalies"
        gateway={gateway}
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Load more financial sources",
      }),
    );
    fireEvent.change(screen.getByLabelText("Active organization"), {
      target: { value: other },
    });
    await screen.findByText("No matching assessments");
    expect(oldSignal.aborted).toBe(true);
    await act(async () =>
      resolve({
        ...initial.sources,
        items: [
          {
            id: "late-private-reference",
            kind: "contract",
            document_id: "private-doc",
          },
        ],
        offset: 100,
      }),
    );
    expect(
      screen.queryByText(/late-private-reference/),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/References loaded: 0 \/ 0/)).toBeInTheDocument();
  });
  it("presents currency totals and explicit missing coverage without recovered-funds claims", async () => {
    const data = await fixture().load(org, signal());
    data.summary.limited = true;
    render(<ExceptionPortfolio data={data} />);
    expect(screen.getByText("12,480.00 USD")).toBeInTheDocument();
    expect(screen.getByText("1,380.00 EUR")).toBeInTheDocument();
    expect(
      screen.getByText(/latest 1,000 evaluations only/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Potential amounts are not recovered funds/),
    ).toBeInTheDocument();
  });
  it("exposes uncertainty explanations and unavailable associations without fabricating a contract", async () => {
    const data = await fixture().load(org, signal()),
      detail = data.assessments.items[0];
    render(
      <ExceptionInvestigation
        detail={{ ...detail, queue_context: undefined }}
        data={data}
        demo
      />,
    );
    expect(
      screen.getByText("No unique approved association returned"),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByText(/Reviewed explanations & uncertainty resolutions/),
    );
    expect(
      screen.getAllByText("Synthetic fixture; not an actual review.").length,
    ).toBeGreaterThan(0);
  });
  it("keeps synthetic reference enrichment isolated with no network call", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch");
    try {
      const gateway = fixture(),
        data = await gateway.load(org, signal());
      expect(data.assessments.items[0].queue_context?.supplier_party).toBe(
        "AcmeCloud",
      );
      await gateway.assessment(org, data.assessments.items[0].id, signal());
      expect(fetcher).not.toHaveBeenCalled();
    } finally {
      fetcher.mockRestore();
    }
  });
});
