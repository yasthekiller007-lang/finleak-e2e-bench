/** Explicit fixture/component contracts. No native SQL or authenticated integration. */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { BusinessFacetSelect } from "@/components/business-facet-select";
import { ServerExceptionsQueue } from "@/components/server-exceptions-queue";
import { ProductConsole } from "@/components/product-console";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import { withSyntheticServerQuery } from "@/lib/product-demo-server-query";
import { withSyntheticBusinessFacets } from "@/lib/product-demo-business-facets";
import {
  liveWorkspaceGateway,
  type WorkspaceGateway,
} from "@/lib/product-workspace";
import {
  facetContext,
  facetsPath,
  type FacetPage,
} from "@/lib/business-facets";
const org = demoUser.organizations[0].id;
const base = () =>
  withSyntheticServerQuery(withSyntheticExceptionContext(createDemoGateway()));
const fixture = () => withSyntheticBusinessFacets(base());
const signal = () => new AbortController().signal;
const empty: FacetPage = {
  facet: "invoice",
  items: [],
  limit: 2,
  has_more: false,
  next_cursor: null,
  order: "synthetic",
  ignored_filter: "invoice_source_id",
  coverage: "Synthetic only",
  consistency: "Synthetic only",
};
const props = (gateway = fixture()) => ({
  gateway,
  org,
  filters: {},
  facet: "invoice" as const,
  selected: null,
  onSelect: vi.fn(),
  demo: true,
  refresh: 0,
});
const queue = (gateway = fixture()) => ({
  gateway,
  org,
  invoice: "",
  reviewOnly: false,
  demo: true,
  onOpen: vi.fn(),
  refresh: 0,
});

it("removes only invoice source and retains the document plus supplier/contract criteria", () => {
  const filters = {
    invoice_source_id: "source",
    invoice_document_id: "document",
    supplier: "Alpha",
    contract_source_id: "contract",
    currency: "USD",
  };
  const context = facetContext(filters, "invoice");
  expect(context.invoice_source_id).toBeUndefined();
  expect(context).toMatchObject({
    invoice_document_id: "document",
    supplier: "Alpha",
    contract_source_id: "contract",
    currency: "USD",
  });
  expect(filters.invoice_source_id).toBe("source");
  const url = new URL(
    facetsPath(filters, "invoice", "INV %_&", 20, "opaque"),
    "https://synthetic.test",
  );
  expect(url.searchParams.get("facet")).toBe("invoice");
  expect(url.searchParams.get("search")).toBe("INV %_&");
  expect(url.searchParams.has("invoice_source_id")).toBe(false);
  expect(url.searchParams.get("invoice_document_id")).toBe("document");
});
it("routes invoice reads through the existing authenticated BFF and never posts decisions", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(Response.json(empty));
  try {
    await liveWorkspaceGateway.queryFacets!(
      org,
      {},
      "invoice",
      "INV",
      20,
      null,
      signal(),
    );
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining(
        `organizations/${org}/financial/exception-facets?facet=invoice`,
      ),
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
    expect(fetcher.mock.calls[0][1]?.body).toBeUndefined();
    expect(fetcher.mock.calls[0][1]?.headers).toBeUndefined();
  } finally {
    fetcher.mockRestore();
  }
});
it("finds an invoice by its actual filename without manufacturing a reference", async () => {
  const response = await fixture().queryFacets!(
    org,
    {},
    "invoice",
    "1042",
    20,
    null,
    signal(),
  );
  expect(response.items).toHaveLength(1);
  expect(response.items[0]).toMatchObject({
    label: "AcmeCloud_INV-2026-1042.pdf",
    reference: null,
    invoice_reference: null,
    reference_basis: "not_available_in_reviewed_schema",
  });
});
it("deduplicates fixture evaluations by source while preserving homonymous document labels", async () => {
  const gateway = base(),
    original = await gateway.queryExceptions!(org, {}, 100, null, signal());
  gateway.queryExceptions = vi.fn().mockResolvedValue({
    ...original,
    items: [
      ...original.items,
      { ...original.items[0], id: "another-evaluation" },
    ].map((r) => ({ ...r, invoice_filename: "SAME-REF.pdf" })),
    has_more: false,
  });
  const result = await withSyntheticBusinessFacets(gateway).queryFacets!(
    org,
    {},
    "invoice",
    "SAME-REF",
    20,
    null,
    signal(),
  );
  expect(result.items).toHaveLength(4);
  expect(new Set(result.items.map((o) => o.value)).size).toBe(4);
  expect(
    result.items.every(
      (o) => o.label === "SAME-REF.pdf" && o.invoice_reference === null,
    ),
  ).toBe(true);
});
it("retains invoice_document_id in the explicitly synthetic fixture", async () => {
  const gateway = fixture(),
    all = await gateway.queryFacets!(
      org,
      {},
      "invoice",
      "",
      20,
      null,
      signal(),
    );
  const choice = all.items[0];
  const filtered = await gateway.queryFacets!(
    org,
    { invoice_source_id: "ignored", invoice_document_id: choice.document_id },
    "invoice",
    "",
    20,
    null,
    signal(),
  );
  expect(filtered.items).toHaveLength(1);
  expect(filtered.items[0].value).toBe(choice.value);
});
it("searches asynchronously and selects a returned document with the keyboard", async () => {
  const p = props();
  render(<BusinessFacetSelect {...p} />);
  const input = screen.getByRole("combobox", { name: "Search invoices" });
  fireEvent.focus(input);
  expect(screen.getByRole("status")).toHaveTextContent("Searching invoices");
  fireEvent.change(input, { target: { value: "1042" } });
  await screen.findByRole("option", { name: /AcmeCloud_INV-2026-1042/ });
  fireEvent.keyDown(input, { key: "Home" });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(p.onSelect).toHaveBeenCalledWith(
    expect.objectContaining({ label: "AcmeCloud_INV-2026-1042.pdf" }),
  );
  expect(input).toHaveAttribute("aria-expanded", "false");
});
it("disambiguates equal names using descriptions and explicitly types dates", async () => {
  const p = props();
  p.gateway.queryFacets = vi.fn().mockResolvedValue({
    ...empty,
    items: [
      {
        value: "internal-one",
        label: "Same.pdf",
        description: "Supplier A · source created 2026-10-19 · choice 1",
        date: "2026-10-01",
        date_type: "reviewed_invoice_date",
      },
      {
        value: "internal-two",
        label: "Same.pdf",
        description: "Supplier A · source created 2026-10-19 · choice 2",
        date: "2026-10-19T00:00:00Z",
        date_type: "reviewed_source_created_at",
      },
    ],
  });
  render(<BusinessFacetSelect {...p} />);
  fireEvent.focus(screen.getByRole("combobox"));
  expect(await screen.findAllByRole("option")).toHaveLength(2);
  expect(
    screen.getByText("Reviewed invoice date: 2026-10-01"),
  ).toBeInTheDocument();
  expect(screen.getByText(/Reviewed source created:/)).toBeInTheDocument();
  expect(screen.queryByText("internal-one")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("option", { name: /choice 2/ }));
  expect(p.onSelect).toHaveBeenCalledWith(
    expect.objectContaining({ value: "internal-two" }),
  );
});
it("shows an empty result and a recoverable error without fake choices", async () => {
  const p = props();
  p.gateway.queryFacets = vi
    .fn()
    .mockRejectedValueOnce(Error("Invoice choices unavailable"))
    .mockResolvedValue(empty);
  render(<BusinessFacetSelect {...p} />);
  fireEvent.focus(screen.getByRole("combobox"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Invoice choices unavailable",
  );
  fireEvent.click(screen.getByRole("button", { name: "Retry choices" }));
  await screen.findByText("No matching invoices for these criteria.");
  expect(screen.queryByRole("option")).not.toBeInTheDocument();
});
it("pages invoice choices and resets the choice cursor after search changes", async () => {
  render(<BusinessFacetSelect {...props()} />);
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(2));
  const before = screen.getAllByRole("option").map((o) => o.textContent);
  fireEvent.click(screen.getByRole("button", { name: "More choices" }));
  await waitFor(() =>
    expect(screen.getAllByRole("option").map((o) => o.textContent)).not.toEqual(
      before,
    ),
  );
  fireEvent.change(input, { target: { value: "1042" } });
  await screen.findByRole("option", { name: /1042/ });
  expect(
    screen.getByRole("button", { name: "Previous choices" }),
  ).toBeDisabled();
});
it("aborts an invoice search when another filter changes and rejects late options", async () => {
  const p = props();
  let resolve!: (page: FacetPage) => void, oldSignal!: AbortSignal;
  p.gateway.queryFacets = vi.fn(
    (_org, filters, _facet, _search, _limit, _after, sig) =>
      filters.currency
        ? Promise.resolve({
            ...empty,
            items: [{ value: "new", label: "NEW.pdf" }],
          })
        : new Promise<FacetPage>((r) => {
            resolve = r;
            oldSignal = sig;
          }),
  );
  const view = render(<BusinessFacetSelect {...p} />);
  fireEvent.focus(screen.getByRole("combobox"));
  await waitFor(() => expect(p.gateway.queryFacets).toHaveBeenCalledTimes(1));
  view.rerender(<BusinessFacetSelect {...p} filters={{ currency: "USD" }} />);
  await screen.findByRole("option", { name: "NEW.pdf" });
  expect(oldSignal.aborted).toBe(true);
  await act(async () =>
    resolve({ ...empty, items: [{ value: "old", label: "OLD.pdf" }] }),
  );
  expect(
    screen.queryByRole("option", { name: "OLD.pdf" }),
  ).not.toBeInTheDocument();
});
it("replaces the technical input, combines invoice/supplier filters and clears the selection", async () => {
  const p = queue(),
    read = vi.spyOn(p.gateway, "queryExceptions"),
    decide = vi.spyOn(p.gateway, "decide");
  render(<ServerExceptionsQueue {...p} />);
  await screen.findByText("4 matching assessments");
  expect(
    screen.queryByLabelText("Server invoice source"),
  ).not.toBeInTheDocument();
  const input = screen.getByRole("combobox", { name: "Search invoices" });
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "1042" } });
  fireEvent.click(await screen.findByRole("option", { name: /1042/ }));
  await screen.findByText("1 matching assessments");
  const selected = read.mock.calls.at(-1)![1].invoice_source_id;
  expect(selected).toBeTruthy();
  fireEvent.focus(screen.getByRole("combobox", { name: "Search suppliers" }));
  fireEvent.click(await screen.findByRole("option", { name: "AcmeCloud" }));
  await waitFor(() =>
    expect(read).toHaveBeenLastCalledWith(
      org,
      expect.objectContaining({
        invoice_source_id: selected,
        supplier: "AcmeCloud",
      }),
      2,
      null,
      expect.any(AbortSignal),
    ),
  );
  expect(input).toHaveValue("AcmeCloud_INV-2026-1042.pdf");
  fireEvent.click(screen.getByRole("button", { name: "Clear invoice" }));
  await screen.findByText("2 matching assessments");
  expect(decide).not.toHaveBeenCalled();
});
it("preserves selected invoice after investigation and back", async () => {
  render(
    <ProductConsole
      user={demoUser}
      view="anomalies"
      gateway={fixture()}
      demo
    />,
  );
  await screen.findByText("4 matching assessments");
  const input = screen.getByRole("combobox", { name: "Search invoices" });
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "1042" } });
  fireEvent.click(await screen.findByRole("option", { name: /1042/ }));
  await screen.findByText("1 matching assessments");
  fireEvent.click(
    within(screen.getByRole("table")).getByRole("button", {
      name: /Investigate/,
    }),
  );
  await screen.findByRole("heading", { name: "Enterprise seats · October" });
  fireEvent.click(screen.getByRole("button", { name: /Back to anomalies/ }));
  expect(screen.getByText("1 matching assessments")).toBeVisible();
  expect(input).toHaveValue("AcmeCloud_INV-2026-1042.pdf");
});
it("keeps a navigation-provided source internal and labels its context without asking for an UUID", async () => {
  const gateway = fixture(),
    records = await gateway.queryExceptions!(org, {}, 100, null, signal());
  const selected = records.items.find((r) =>
    r.invoice_filename?.includes("1042"),
  )!;
  render(
    <ServerExceptionsQueue
      {...queue(gateway)}
      invoice={selected.invoice_source_id}
    />,
  );
  await screen.findByText("1 matching assessments");
  expect(screen.getByRole("combobox", { name: "Search invoices" })).toHaveValue(
    "AcmeCloud_INV-2026-1042.pdf",
  );
  expect(
    screen.queryByDisplayValue(selected.invoice_source_id),
  ).not.toBeInTheDocument();
});
it("retains selected invoice identity and a mocked second-page position after investigation", async () => {
  const gateway = fixture(),
    query = gateway.queryExceptions!;
  gateway.queryExceptions = vi.fn(
    async (
      ...args: Parameters<NonNullable<WorkspaceGateway["queryExceptions"]>>
    ) => {
      const page = await query(args[0], args[1], args[2], null, args[4]);
      if (!args[1].invoice_source_id) return page;
      const item = page.items[0];
      return {
        ...page,
        items: [item],
        total: 2,
        offset: args[3] ? 1 : 0,
        has_more: !args[3],
        next_cursor: args[3] ? null : "explicit-mocked-second-page",
      };
    },
  );
  render(
    <ProductConsole user={demoUser} view="anomalies" gateway={gateway} demo />,
  );
  await screen.findByText("4 matching assessments");
  fireEvent.focus(screen.getByRole("combobox", { name: "Search invoices" }));
  fireEvent.change(screen.getByRole("combobox", { name: "Search invoices" }), {
    target: { value: "1042" },
  });
  fireEvent.click(await screen.findByRole("option", { name: /1042/ }));
  await screen.findByText(/1–1 of 2/);
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  await screen.findByText(/2–2 of 2/);
  fireEvent.click(
    within(screen.getByRole("table")).getByRole("button", {
      name: /Investigate/,
    }),
  );
  fireEvent.click(
    await screen.findByRole("button", { name: /Back to anomalies/ }),
  );
  expect(screen.getByText(/2–2 of 2/)).toBeVisible();
  expect(screen.getByRole("combobox", { name: "Search invoices" })).toHaveValue(
    "AcmeCloud_INV-2026-1042.pdf",
  );
});
