/** Contract/component tests with explicit fixtures. No SQL, OIDC or PostgreSQL integration. */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BusinessFacetSelect } from "@/components/business-facet-select";
import { ServerExceptionsQueue } from "@/components/server-exceptions-queue";
import { ProductConsole } from "@/components/product-console";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import { withSyntheticServerQuery } from "@/lib/product-demo-server-query";
import { withSyntheticBusinessFacets } from "@/lib/product-demo-business-facets";
import { liveWorkspaceGateway } from "@/lib/product-workspace";
import { facetsPath, type FacetPage } from "@/lib/business-facets";
const org = demoUser.organizations[0].id;
const fixture = () =>
  withSyntheticBusinessFacets(
    withSyntheticServerQuery(
      withSyntheticExceptionContext(createDemoGateway()),
    ),
  );
const signal = () => new AbortController().signal;
const result = (labels: string[]): FacetPage => ({
  facet: "supplier",
  items: labels.map((label) => ({ label, value: label })),
  limit: 2,
  has_more: false,
  next_cursor: null,
  order: "synthetic",
  ignored_filter: "supplier",
  coverage: "Synthetic",
  consistency: "Synthetic",
});
const selector = (gateway = fixture()) => ({
  gateway,
  org,
  filters: {},
  facet: "supplier" as const,
  selected: null,
  onSelect: vi.fn(),
  demo: true,
  refresh: 0,
});
const queue = (gateway = fixture()) => ({
  gateway,
  org,
  reviewOnly: false,
  invoice: "",
  onOpen: vi.fn(),
  demo: true,
  refresh: 0,
});

describe("business facet contracts", () => {
  it("encodes the scoped route and removes only its own selection", () => {
    const path = facetsPath(
      {
        supplier: "Alpha",
        contract_source_id: "internal",
        currency: "USD",
        missing_contract: true,
        current: true,
      },
      "supplier",
      "a%_ &",
      20,
      "cursor",
    );
    const url = new URL(path, "https://synthetic.test");
    expect(url.pathname).toBe("/financial/exception-facets");
    expect(url.searchParams.has("supplier")).toBe(false);
    expect(url.searchParams.get("contract_source_id")).toBe("internal");
    expect(url.searchParams.get("search")).toBe("a%_ &");
    expect(url.searchParams.get("missing_contract")).toBe("true");
    expect(url.searchParams.get("after")).toBe("cursor");
    expect(
      new URL(
        facetsPath(
          { supplier: "A", contract_source_id: "internal" },
          "contract",
          "",
          20,
          null,
        ),
        "https://synthetic.test",
      ).searchParams.get("supplier"),
    ).toBe("A");
  });
  it("uses the existing same-origin authenticated BFF without a browser token", async () => {
    const mock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json(result(["Alpha"])));
    try {
      await expect(
        liveWorkspaceGateway.queryFacets!(
          org,
          { currency: "USD" },
          "supplier",
          "Alpha",
          20,
          null,
          signal(),
        ),
      ).resolves.toEqual(result(["Alpha"]));
      expect(mock).toHaveBeenCalledWith(
        expect.stringContaining(
          `/api/organizations/${org}/financial/exception-facets?facet=supplier`,
        ),
        expect.objectContaining({
          credentials: "same-origin",
          cache: "no-store",
        }),
      );
      expect(mock.mock.calls[0][1]?.headers).toBeUndefined();
    } finally {
      mock.mockRestore();
    }
  });
  it("preserves explicit facet restart messages on HTTP 409", async () => {
    const mock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json(
        {
          error: {
            code: "FACETS_CHANGED",
            message: "Financial records changed; restart the choices",
          },
        },
        { status: 409 },
      ),
    );
    try {
      await expect(
        liveWorkspaceGateway.queryFacets!(
          org,
          {},
          "supplier",
          "",
          20,
          "old",
          signal(),
        ),
      ).rejects.toMatchObject({
        status: 409,
        message: "Financial records changed; restart the choices",
      });
    } finally {
      mock.mockRestore();
    }
  });
  it("demonstrates bounded fixture paging, exact string identities and missing-contract semantics", async () => {
    const gateway = fixture();
    const first = await gateway.queryFacets!(
      org,
      {},
      "supplier",
      "",
      2,
      null,
      signal(),
    );
    expect(first.items.map((o) => o.label)).toEqual(["AcmeCloud", "Atlas"]);
    expect(first.has_more).toBe(true);
    const next = await gateway.queryFacets!(
      org,
      {},
      "supplier",
      "",
      2,
      first.next_cursor,
      signal(),
    );
    expect(next.items.map((o) => o.label)).toEqual(["Veridian"]);
    const empty = await gateway.queryFacets!(
      org,
      { missing_contract: true },
      "contract",
      "",
      2,
      null,
      signal(),
    );
    expect(empty.items).toEqual([]);
    expect("total" in first).toBe(false);
  });
});

describe("asynchronous accessible facet selector", () => {
  it("searches asynchronously, selects with the keyboard and clears without manual UUID input", async () => {
    const props = selector();
    render(<BusinessFacetSelect {...props} />);
    const input = screen.getByRole("combobox", { name: "Search suppliers" });
    fireEvent.focus(input);
    expect(screen.getByRole("status")).toHaveTextContent("Searching suppliers");
    fireEvent.change(input, { target: { value: "Acme" } });
    await screen.findByRole("option", { name: "AcmeCloud" });
    fireEvent.keyDown(input, { key: "Home" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(props.onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ value: "AcmeCloud" }),
    );
    expect(input).toHaveAttribute("aria-expanded", "false");
  });
  it("renders repeated references with document descriptions and internal IDs never become visible labels", async () => {
    const props = { ...selector(), facet: "contract" as const };
    props.gateway.queryFacets = vi.fn().mockResolvedValue({
      ...result([]),
      facet: "contract",
      items: [
        {
          value: "internal-one",
          label: "REF-2026",
          description: "Master.pdf · choice 1",
        },
        {
          value: "internal-two",
          label: "REF-2026",
          description: "Schedule.pdf · choice 2",
        },
      ],
    });
    render(<BusinessFacetSelect {...props} />);
    fireEvent.focus(screen.getByRole("combobox"));
    expect(await screen.findAllByRole("option")).toHaveLength(2);
    expect(screen.getByText("Master.pdf · choice 1")).toBeInTheDocument();
    expect(screen.queryByText(/internal-one/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: /Schedule/ }));
    expect(props.onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ value: "internal-two" }),
    );
  });
  it("cancels a late result after a search change and does not display its options", async () => {
    const props = selector();
    let resolve!: (page: FacetPage) => void, oldSignal!: AbortSignal;
    props.gateway.queryFacets = vi.fn(
      (_org, _filters, _facet, search, _limit, _after, sig) =>
        search
          ? Promise.resolve(result(["NEW"]))
          : new Promise<FacetPage>((r) => {
              resolve = r;
              oldSignal = sig;
            }),
    );
    render(<BusinessFacetSelect {...props} />);
    fireEvent.focus(screen.getByRole("combobox"));
    await waitFor(() =>
      expect(props.gateway.queryFacets).toHaveBeenCalledTimes(1),
    );
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "new" },
    });
    await screen.findByRole("option", { name: "NEW" });
    expect(oldSignal.aborted).toBe(true);
    await act(async () => resolve(result(["STALE"])));
    expect(
      screen.queryByRole("option", { name: "STALE" }),
    ).not.toBeInTheDocument();
  });
  it("suppresses old tenant choices and scopes the new read", async () => {
    const props = selector();
    let resolve!: (page: FacetPage) => void;
    props.gateway.queryFacets = vi.fn((id) =>
      id === org
        ? new Promise<FacetPage>((r) => {
            resolve = r;
          })
        : Promise.resolve(result(["OTHER-TENANT"])),
    );
    const view = render(<BusinessFacetSelect {...props} />);
    fireEvent.focus(screen.getByRole("combobox"));
    await waitFor(() =>
      expect(props.gateway.queryFacets).toHaveBeenCalledTimes(1),
    );
    view.rerender(<BusinessFacetSelect {...props} org="other-org-fixture" />);
    await screen.findByRole("option", { name: "OTHER-TENANT" });
    await act(async () => resolve(result(["OLD-TENANT"])));
    expect(
      screen.queryByRole("option", { name: "OLD-TENANT" }),
    ).not.toBeInTheDocument();
  });
  it("pages choices, resets on search and reports an explicit empty result", async () => {
    const props = selector();
    render(<BusinessFacetSelect {...props} />);
    fireEvent.focus(screen.getByRole("combobox"));
    await screen.findByRole("option", { name: "Atlas" });
    fireEvent.click(screen.getByRole("button", { name: "More choices" }));
    await screen.findByRole("option", { name: "Veridian" });
    expect(
      screen.queryByRole("option", { name: "Atlas" }),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "nothing" },
    });
    await screen.findByText("No matching supplier strings for these criteria.");
    expect(
      screen.getByRole("button", { name: "Previous choices" }),
    ).toBeDisabled();
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });
    expect(screen.getByRole("combobox")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });
  it("shows recoverable errors and explicit dynamic-limit failures without fallback choices", async () => {
    const props = selector();
    props.gateway.queryFacets = vi
      .fn()
      .mockRejectedValueOnce(Error("100 SQL candidates required"))
      .mockResolvedValueOnce(result(["RECOVERED"]));
    render(<BusinessFacetSelect {...props} />);
    fireEvent.focus(screen.getByRole("combobox"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "100 SQL candidates",
    );
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry choices" }));
    await screen.findByRole("option", { name: "RECOVERED" });
  });
});

describe("queue business selection integration", () => {
  it("sends only a returned supplier value, combines filters and restarts the results page", async () => {
    const props = queue(),
      query = vi.spyOn(props.gateway, "queryExceptions");
    render(<ServerExceptionsQueue {...props} />);
    await screen.findByText("4 matching assessments");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText(/3–4 of 4/);
    fireEvent.focus(screen.getByRole("combobox", { name: "Search suppliers" }));
    fireEvent.change(
      screen.getByRole("combobox", { name: "Search suppliers" }),
      { target: { value: "Acme" } },
    );
    fireEvent.click(await screen.findByRole("option", { name: "AcmeCloud" }));
    fireEvent.change(screen.getByLabelText("Server currency"), {
      target: { value: "USD" },
    });
    await screen.findByText("2 matching assessments");
    expect(query).toHaveBeenLastCalledWith(
      org,
      expect.objectContaining({ supplier: "AcmeCloud", currency: "USD" }),
      2,
      null,
      expect.any(AbortSignal),
    );
    expect(
      screen.queryByLabelText("Server contract source"),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Server supplier")).not.toBeInTheDocument();
  });
  it("selects a readable contract, clears it on supplier change and refreshes relevant choices", async () => {
    const props = queue();
    render(<ServerExceptionsQueue {...props} />);
    await screen.findByText("4 matching assessments");
    const contract = screen.getByRole("combobox", {
      name: "Search approved contracts",
    });
    fireEvent.focus(contract);
    fireEvent.click(
      (
        await within(
          await screen.findByRole("listbox", {
            name: "Approved contract choices",
          }),
        ).findAllByRole("option")
      )[0],
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Clear approved contract" }),
      ).toBeInTheDocument(),
    );
    fireEvent.focus(screen.getByRole("combobox", { name: "Search suppliers" }));
    fireEvent.click(
      (
        await within(
          await screen.findByRole("listbox", { name: "Supplier choices" }),
        ).findAllByRole("option")
      )[0],
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Clear approved contract" }),
      ).not.toBeInTheDocument(),
    );
    fireEvent.focus(contract);
    await within(
      await screen.findByRole("listbox", { name: "Approved contract choices" }),
    ).findAllByRole("option");
    expect(contract).toHaveValue("");
  });
  it("preserves the selected supplier and exact cursor position after investigation and back", async () => {
    render(
      <ProductConsole
        user={demoUser}
        view="anomalies"
        gateway={fixture()}
        demo
      />,
    );
    await screen.findByText("4 matching assessments");
    fireEvent.change(screen.getByLabelText("Server page size"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText(/3–4 of 4/);
    const visible = within(screen.getByRole("table")).getAllByRole("button", {
      name: /Investigate/,
    });
    fireEvent.click(visible[0]);
    await screen.findByRole("button", { name: /Back to anomalies/ });
    fireEvent.click(screen.getByRole("button", { name: /Back to anomalies/ }));
    expect(screen.getByText(/3–4 of 4/)).toBeVisible();
    fireEvent.focus(screen.getByRole("combobox", { name: "Search suppliers" }));
    fireEvent.change(
      screen.getByRole("combobox", { name: "Search suppliers" }),
      { target: { value: "Acme" } },
    );
    fireEvent.click(await screen.findByRole("option", { name: "AcmeCloud" }));
    await screen.findByText("2 matching assessments");
    fireEvent.click(
      within(screen.getByRole("table")).getAllByRole("button", {
        name: /Investigate/,
      })[0],
    );
    fireEvent.click(
      await screen.findByRole("button", { name: /Back to anomalies/ }),
    );
    expect(
      screen.getByRole("combobox", { name: "Search suppliers" }),
    ).toHaveValue("AcmeCloud");
    expect(screen.getByText("2 matching assessments")).toBeVisible();
  });
});

it("reopens a focused selector after choosing and requests fresh options", async () => {
  const props = selector(),
    query = vi.spyOn(props.gateway, "queryFacets");
  render(<BusinessFacetSelect {...props} />);
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.click(await screen.findByRole("option", { name: "AcmeCloud" }));
  expect(input).toHaveAttribute("aria-expanded", "false");
  const before = query.mock.calls.length;
  fireEvent.click(input);
  expect(input).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("status")).toHaveTextContent("Searching");
  await screen.findByRole("option", { name: "AcmeCloud" });
  expect(query.mock.calls.length).toBe(before + 1);
});

it("clears an explicit selection and retains exact case and spacing in option values", async () => {
  const props = { ...selector(), selected: { value: "ACME ", label: "ACME " } };
  props.gateway.queryFacets = vi
    .fn()
    .mockResolvedValue(result(["ACME", "ACME ", "Acme"]));
  render(<BusinessFacetSelect {...props} />);
  fireEvent.click(screen.getByRole("button", { name: "Clear supplier" }));
  expect(props.onSelect).toHaveBeenCalledWith(null);
  fireEvent.focus(screen.getByRole("combobox"));
  const options = await screen.findAllByRole("option");
  expect(options).toHaveLength(3);
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "Home" });
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "ArrowDown" });
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" });
  expect(props.onSelect).toHaveBeenLastCalledWith({
    value: "ACME ",
    label: "ACME ",
  });
});
