/** Component/gateway doubles only; no real identity provider or PostgreSQL persistence. */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ExceptionViewWorkspace } from "@/components/exception-view-workspace";
import { PersonalSavedViews } from "@/components/personal-saved-views";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import { withSyntheticServerQuery } from "@/lib/product-demo-server-query";
import { withSyntheticBusinessFacets } from "@/lib/product-demo-business-facets";
import { withSyntheticSavedViews } from "@/lib/product-demo-saved-views";
import {
  savedDefinition,
  SavedViewsError,
  type SavedView,
} from "@/lib/saved-views";
import { WorkspaceError } from "@/lib/product-workspace";
import { viewPath } from "@/lib/exception-view-url";
const org = demoUser.organizations[0].id,
  owner = demoUser.id;
const fixture = (seed = false) =>
  withSyntheticSavedViews(
    withSyntheticBusinessFacets(
      withSyntheticServerQuery(
        withSyntheticExceptionContext(createDemoGateway()),
      ),
    ),
    seed,
  );
const panel = () =>
  within(screen.getByRole("region", { name: "My saved views" }));
const signal = () => new AbortController().signal;
const definition = savedDefinition(
  {
    view_type: "anomalies",
    format_version: 1,
    criteria: { currency: "USD" },
    page_size: 2,
  },
  true,
);
afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.restoreAllMocks();
});
function open(gateway = fixture(), view: "anomalies" | "review" = "anomalies") {
  window.history.replaceState({}, "", viewPath(org, {}, 2, view, true));
  const rendered = render(
    <ExceptionViewWorkspace
      user={demoUser}
      view={view}
      demo
      gateway={gateway}
    />,
  );
  return { gateway, ...rendered };
}
async function ready() {
  await waitFor(
    () =>
      expect(
        panel().getByRole("button", { name: "Save current view" }),
      ).toBeEnabled(),
    { timeout: 5000 },
  );
}
async function save(name = "CFO USD") {
  fireEvent.click(panel().getByRole("button", { name: "Save current view" }));
  fireEvent.change(
    panel().getByRole("textbox", { name: "New saved view name" }),
    { target: { value: name } },
  );
  fireEvent.click(panel().getByRole("button", { name: "Save named view" }));
  await waitFor(() =>
    expect(
      panel().getByText(/Synthetic view saved in this demo only/),
    ).toBeInTheDocument(),
  );
}
async function seed(gateway = fixture(), name = "CFO USD") {
  const row = await gateway.savedViews!.create(
    org,
    owner,
    name,
    definition,
    signal(),
  );
  return { gateway, row };
}
it("saves only acknowledged criteria and shows a real gateway acknowledgment without a persistence claim", async () => {
  const { gateway } = open();
  const create = vi.spyOn(gateway.savedViews!, "create");
  const decide = vi.spyOn(gateway, "decide");
  await ready();
  await save();
  expect(create).toHaveBeenCalledTimes(1);
  const args = create.mock.calls[0];
  expect(args[0]).toBe(org);
  expect(args[1]).toBe(owner);
  expect(args[3]).toMatchObject({
    format_version: 1,
    view_type: "anomalies",
    page_size: 2,
  });
  expect(args[3]).not.toHaveProperty("after");
  expect(args[3]).not.toHaveProperty("potential");
  expect(decide).not.toHaveBeenCalled();
  await waitFor(() =>
    expect(
      panel().getByRole("button", { name: "Open saved view CFO USD" }),
    ).toBeEnabled(),
  );
});
it("requires a valid name and never posts an empty one", async () => {
  const { gateway } = open();
  const create = vi.spyOn(gateway.savedViews!, "create");
  await ready();
  fireEvent.click(panel().getByRole("button", { name: "Save current view" }));
  fireEvent.click(panel().getByRole("button", { name: "Save named view" }));
  expect(panel().getByRole("alert")).toHaveTextContent("between 1 and 80");
  expect(create).not.toHaveBeenCalled();
});
it("waits for authoritative success and prevents rapid double submission", async () => {
  const { gateway } = open();
  let resolve!: (r: SavedView) => void;
  const original = gateway.savedViews!.create.bind(gateway.savedViews);
  const response = await original(org, owner, "CFO USD", definition, signal());
  const create = vi.spyOn(gateway.savedViews!, "create").mockImplementation(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  await ready();
  fireEvent.click(panel().getByRole("button", { name: "Save current view" }));
  fireEvent.change(
    panel().getByRole("textbox", { name: "New saved view name" }),
    { target: { value: "CFO USD" } },
  );
  const button = panel().getByRole("button", { name: "Save named view" });
  act(() => {
    fireEvent.click(button);
    fireEvent.click(button);
  });
  expect(create).toHaveBeenCalledTimes(1);
  expect(
    panel().queryByText(/Synthetic view saved in this demo only/),
  ).not.toBeInTheDocument();
  await act(async () => resolve(response));
  expect(
    panel().getByText(/Synthetic view saved in this demo only/),
  ).toBeInTheDocument();
});
it("disables saving during edits and on failed financial reads, retaining the last URL", async () => {
  const { gateway } = open();
  await ready();
  const before = window.location.search;
  vi.spyOn(gateway, "queryExceptions").mockRejectedValue(
    new Error("Synthetic read failed"),
  );
  fireEvent.change(screen.getByRole("textbox", { name: "Server currency" }), {
    target: { value: "USD" },
  });
  expect(
    panel().getByRole("button", { name: "Save current view" }),
  ).toBeDisabled();
  await screen.findByText("Synthetic read failed");
  expect(
    panel().getByRole("button", { name: "Save current view" }),
  ).toBeDisabled();
  expect(window.location.search).toBe(before);
});
it("does not save when applied criteria and browser URL disagree", async () => {
  open();
  await ready();
  window.history.replaceState(
    {},
    "",
    "/demo/anomalies?ev=1&org=" + org + "&ev_currency=EUR",
  );
  fireEvent.click(panel().getByRole("button", { name: "Save current view" }));
  expect(
    panel().queryByRole("textbox", { name: "New saved view name" }),
  ).not.toBeInTheDocument();
});
it("opens from the authorized API then reuses a fresh first-page server query", async () => {
  const { gateway } = await seed();
  const get = vi.spyOn(gateway.savedViews!, "get");
  open(gateway);
  const query = vi.spyOn(gateway, "queryExceptions");
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Previous page" })).toBeEnabled(),
  );
  const count = query.mock.calls.length;
  fireEvent.click(
    panel().getByRole("button", { name: "Open saved view CFO USD" }),
  );
  await waitFor(() =>
    expect(window.location.search).toContain("ev_currency=USD"),
  );
  expect(get).toHaveBeenCalledTimes(1);
  expect(query.mock.calls.length).toBeGreaterThan(count);
  expect(query.mock.calls.at(-1)![3]).toBeNull();
  expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
  expect(
    panel().getByText(/Consult the queue for the fresh search result/),
  ).toBeInTheDocument();
});
it("opening an identical view still performs a new financial read", async () => {
  const gateway = fixture();
  await gateway.savedViews!.create(
    org,
    owner,
    "Default",
    savedDefinition({ ...definition, criteria: {} }, true),
    signal(),
  );
  open(gateway);
  const query = vi.spyOn(gateway, "queryExceptions");
  await ready();
  const count = query.mock.calls.length;
  fireEvent.click(
    panel().getByRole("button", { name: "Open saved view Default" }),
  );
  await waitFor(() => expect(query.mock.calls.length).toBeGreaterThan(count));
});
it("renames without replacing criteria and requires explicit update confirmation", async () => {
  const { gateway } = await seed();
  const update = vi.spyOn(gateway.savedViews!, "update");
  open(gateway);
  await ready();
  fireEvent.click(
    panel().getByRole("button", { name: "Manage saved view CFO USD" }),
  );
  await screen.findByRole("textbox", { name: "Rename personal view" });
  fireEvent.change(
    panel().getByRole("textbox", { name: "Rename personal view" }),
    { target: { value: "CFO renamed" } },
  );
  fireEvent.click(panel().getByRole("button", { name: "Rename view" }));
  await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
  expect(update.mock.calls[0][4]).toEqual({ name: "CFO renamed" });
  await waitFor(() =>
    expect(
      panel().getByRole("button", { name: "Update saved criteria" }),
    ).toBeEnabled(),
  );
  fireEvent.click(
    panel().getByRole("button", { name: "Update saved criteria" }),
  );
  expect(update).toHaveBeenCalledTimes(1);
  fireEvent.click(
    panel().getByRole("button", { name: "Confirm update criteria" }),
  );
  await waitFor(() => expect(update).toHaveBeenCalledTimes(2));
  expect(update.mock.calls[1][4]).toHaveProperty("definition");
  expect(update.mock.calls[1][3]).toBe(2);
});
it("requires deletion confirmation and preserves financial data and decisions", async () => {
  const { gateway } = await seed();
  const remove = vi.spyOn(gateway.savedViews!, "remove"),
    decide = vi.spyOn(gateway, "decide");
  open(gateway);
  await ready();
  fireEvent.click(
    panel().getByRole("button", { name: "Manage saved view CFO USD" }),
  );
  await screen.findByRole("textbox", { name: "Rename personal view" });
  fireEvent.click(
    panel().getByRole("button", { name: "Delete personal view" }),
  );
  expect(remove).not.toHaveBeenCalled();
  fireEvent.click(panel().getByRole("button", { name: "Cancel change" }));
  expect(remove).not.toHaveBeenCalled();
  fireEvent.click(
    panel().getByRole("button", { name: "Delete personal view" }),
  );
  fireEvent.click(
    panel().getByRole("button", { name: "Confirm delete personal view" }),
  );
  await waitFor(() =>
    expect(panel().getByText(/removed from memory only/)).toBeInTheDocument(),
  );
  expect(remove).toHaveBeenCalledTimes(1);
  expect(decide).not.toHaveBeenCalled();
  expect(
    await gateway.savedViews!.list(org, owner, "anomalies", "", null, signal()),
  ).toMatchObject({ items: [] });
});
it("retains a rename draft after 409, performs no automatic write retry and offers re-read", async () => {
  const { gateway } = await seed();
  const update = vi
    .spyOn(gateway.savedViews!, "update")
    .mockRejectedValue(new SavedViewsError("Synthetic conflict", 409));
  open(gateway);
  await ready();
  fireEvent.click(
    panel().getByRole("button", { name: "Manage saved view CFO USD" }),
  );
  await screen.findByRole("textbox", { name: "Rename personal view" });
  fireEvent.change(
    panel().getByRole("textbox", { name: "Rename personal view" }),
    { target: { value: "Keep my draft" } },
  );
  fireEvent.click(panel().getByRole("button", { name: "Rename view" }));
  await waitFor(() =>
    expect(panel().getByRole("alert")).toHaveTextContent(
      "No automatic write retry",
    ),
  );
  expect(
    panel().getByRole("textbox", { name: "Rename personal view" }),
  ).toHaveValue("Keep my draft");
  expect(panel().getByRole("button", { name: "Rename view" })).toBeDisabled();
  expect(update).toHaveBeenCalledTimes(1);
  fireEvent.click(
    panel().getByRole("button", { name: "Reload personal views" }),
  );
  await waitFor(() =>
    expect(panel().getByRole("button", { name: "Rename view" })).toBeEnabled(),
  );
  expect(
    panel().getByRole("textbox", { name: "Rename personal view" }),
  ).toHaveValue("Keep my draft");
  expect(update).toHaveBeenCalledTimes(1);
});
it("does not claim success or replay creation after a lost response; reload recovers the recorded view", async () => {
  const { gateway } = open();
  const original = gateway.savedViews!.create.bind(gateway.savedViews);
  const create = vi
    .spyOn(gateway.savedViews!, "create")
    .mockImplementation(async (...args) => {
      await original(...args);
      throw new Error("Synthetic lost response; outcome unknown");
    });
  await ready();
  fireEvent.click(panel().getByRole("button", { name: "Save current view" }));
  fireEvent.change(
    panel().getByRole("textbox", { name: "New saved view name" }),
    { target: { value: "Lost response view" } },
  );
  fireEvent.click(panel().getByRole("button", { name: "Save named view" }));
  await waitFor(() =>
    expect(panel().getByRole("alert")).toHaveTextContent("outcome unknown"),
  );
  expect(
    panel().queryByText(/Synthetic view saved in this demo only/),
  ).not.toBeInTheDocument();
  expect(create).toHaveBeenCalledTimes(1);
  fireEvent.click(
    panel().getByRole("button", { name: "Reload personal views" }),
  );
  await screen.findByRole("button", {
    name: "Open saved view Lost response view",
  });
  expect(create).toHaveBeenCalledTimes(1);
});
it("searches names asynchronously and paginates without loading all views", async () => {
  const gateway = fixture();
  for (let i = 0; i < 12; i++)
    await gateway.savedViews!.create(
      org,
      owner,
      `View ${i}`,
      definition,
      signal(),
    );
  const listing = vi.spyOn(gateway.savedViews!, "list");
  open(gateway);
  await ready();
  await screen.findByRole("button", { name: "Open saved view View 0" });
  expect(
    panel().getAllByRole("button", { name: /^Open saved view/ }),
  ).toHaveLength(10);
  fireEvent.click(panel().getByRole("button", { name: "More saved views" }));
  await screen.findByRole("button", { name: "Open saved view View 11" });
  expect(
    panel().getAllByRole("button", { name: /^Open saved view/ }),
  ).toHaveLength(2);
  fireEvent.change(
    panel().getByRole("textbox", { name: "Find personal views" }),
    { target: { value: "View 7" } },
  );
  await screen.findByRole("button", { name: "Open saved view View 7" });
  expect(listing.mock.calls.at(-1)![4]).toBeNull();
  expect(
    panel().getAllByRole("button", { name: /^Open saved view/ }),
  ).toHaveLength(1);
});
it("ignores late name-search responses", async () => {
  const { gateway, row } = await seed();
  const original = gateway.savedViews!.list.bind(gateway.savedViews);
  let resolve!: (value: Awaited<ReturnType<typeof original>>) => void;
  vi.spyOn(gateway.savedViews!, "list").mockImplementation((...args) =>
    args[3] === "slow"
      ? new Promise((r) => {
          resolve = r;
        })
      : original(...args),
  );
  open(gateway);
  await ready();
  fireEvent.change(
    panel().getByRole("textbox", { name: "Find personal views" }),
    { target: { value: "slow" } },
  );
  await waitFor(() => expect(resolve).toBeDefined());
  fireEvent.change(
    panel().getByRole("textbox", { name: "Find personal views" }),
    { target: { value: "nothing" } },
  );
  await screen.findByText(/No personal views match/);
  await act(async () =>
    resolve({
      items: [row],
      limit: 10,
      has_more: false,
      next_after: null,
      max_views: 50,
    }),
  );
  expect(
    panel().queryByRole("button", { name: "Open saved view CFO USD" }),
  ).not.toBeInTheDocument();
});
it("does not substitute an unavailable source when opening a view", async () => {
  const gateway = fixture();
  const missing = "00000000-0000-4000-8000-000000000999";
  await gateway.savedViews!.create(
    org,
    owner,
    "Missing source",
    savedDefinition(
      { ...definition, criteria: { invoice_source_id: missing } },
      true,
    ),
    signal(),
  );
  open(gateway);
  const query = vi.spyOn(gateway, "queryExceptions");
  await ready();
  fireEvent.click(
    panel().getByRole("button", { name: "Open saved view Missing source" }),
  );
  await waitFor(() => expect(window.location.search).toContain(missing));
  expect(query.mock.calls.at(-1)![1].invoice_source_id).toBe(missing);
  expect(screen.getByRole("combobox", { name: "Search invoices" })).toHaveValue(
    "Selected invoice label unavailable",
  );
});
it("refuses unknown format on re-read without starting a financial query", async () => {
  const { gateway, row } = await seed();
  vi.spyOn(gateway.savedViews!, "get").mockResolvedValue({
    ...row,
    format_version: 2,
  } as unknown as SavedView);
  open(gateway);
  const query = vi.spyOn(gateway, "queryExceptions");
  await ready();
  const count = query.mock.calls.length;
  fireEvent.click(
    panel().getByRole("button", { name: "Open saved view CFO USD" }),
  );
  await waitFor(() =>
    expect(panel().getByRole("alert")).toHaveTextContent(
      "Unsupported personal view",
    ),
  );
  expect(query).toHaveBeenCalledTimes(count);
});
it("bounds list retry to an explicit action", async () => {
  const gateway = fixture();
  const listing = vi
    .spyOn(gateway.savedViews!, "list")
    .mockRejectedValueOnce(Error("Synthetic unavailable"));
  open(gateway);
  await screen.findByRole("button", { name: "Retry personal views" });
  expect(listing).toHaveBeenCalledTimes(1);
  fireEvent.click(
    panel().getByRole("button", { name: "Retry personal views" }),
  );
  await screen.findByText(/No personal views match/);
  expect(listing).toHaveBeenCalledTimes(2);
});
it("preserves review defaults in a newly saved review view", async () => {
  const { gateway } = open(fixture(), "review");
  const create = vi.spyOn(gateway.savedViews!, "create");
  await ready();
  await save("Review defaults");
  expect(create.mock.calls[0][3]).toMatchObject({
    view_type: "review",
    criteria: { needs_review: true },
  });
});
it("clears the personal panel when current membership disappears", async () => {
  const { gateway } = await seed();
  const r = open(gateway);
  await ready();
  await screen.findByRole("button", { name: "Open saved view CFO USD" });
  r.rerender(
    <ExceptionViewWorkspace
      user={{ ...demoUser, organizations: [] }}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  expect(
    screen.queryByRole("region", { name: "My saved views" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "View unavailable" }),
  ).toBeInTheDocument();
});
it("rejects a cross-user gateway response and never renders its private name", async () => {
  const { gateway, row } = await seed();
  vi.spyOn(gateway.savedViews!, "list").mockResolvedValue({
    items: [{ ...row, user_id: "other-user", name: "Private other user" }],
    limit: 10,
    has_more: false,
    next_after: null,
    max_views: 50,
  });
  open(gateway);
  await screen.findByRole("button", { name: "Retry personal views" });
  expect(screen.queryByText("Private other user")).not.toBeInTheDocument();
});
it("cancels personal requests on organization change and does not expose old-user views", async () => {
  const { gateway } = await seed();
  let seen: AbortSignal | undefined;
  vi.spyOn(gateway.savedViews!, "get").mockImplementation((_o, _u, _i, s) => {
    seen = s;
    return new Promise(() => {});
  });
  const r = open(gateway);
  await ready();
  fireEvent.click(
    panel().getByRole("button", { name: "Open saved view CFO USD" }),
  );
  await waitFor(() => expect(seen).toBeDefined());
  r.rerender(
    <ExceptionViewWorkspace
      user={{ ...demoUser, id: "00000000-0000-4000-8000-000000000999" }}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  expect(seen!.aborted).toBe(true);
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Open saved view CFO USD" }),
    ).not.toBeInTheDocument(),
  );
});
it("keeps the original URL when a saved search fails and never reports financial success", async () => {
  const { gateway } = await seed();
  open(gateway);
  await ready();
  const before = window.location.search;
  vi.spyOn(gateway, "queryExceptions").mockRejectedValue(
    new WorkspaceError("Synthetic candidate limit", 422),
  );
  fireEvent.click(
    panel().getByRole("button", { name: "Open saved view CFO USD" }),
  );
  await screen.findByText("Synthetic candidate limit");
  expect(window.location.search).toBe(before);
  expect(
    panel().getByRole("button", { name: "Save current view" }),
  ).toBeDisabled();
});
it("never exposes or writes personal views when authorization is absent", () => {
  const gateway = fixture().savedViews!;
  const listing = vi.spyOn(gateway, "list");
  render(
    <PersonalSavedViews
      gateway={gateway}
      org={org}
      owner={owner}
      view="anomalies"
      demo
      authorized={false}
      canSave
      getCurrent={() => definition}
      onOpen={() => true}
    />,
  );
  expect(
    screen.getByRole("button", { name: "Save current view" }),
  ).toBeDisabled();
  expect(listing).not.toHaveBeenCalled();
});
