/** Explicit synthetic/component boundaries. No OIDC or PostgreSQL integration claim. */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ExceptionViewWorkspace } from "@/components/exception-view-workspace";
import { ServerExceptionsQueue } from "@/components/server-exceptions-queue";
import { BusinessFacetSelect } from "@/components/business-facet-select";
import { SourceFacetSelect } from "@/components/source-facet-select";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import { withSyntheticServerQuery } from "@/lib/product-demo-server-query";
import { withSyntheticBusinessFacets } from "@/lib/product-demo-business-facets";
import { liveWorkspaceGateway, WorkspaceError } from "@/lib/product-workspace";
import { viewPath } from "@/lib/exception-view-url";
import { cursorNeedsRestart } from "@/lib/cursor-recovery";
const org = demoUser.organizations[0].id,
  other = "00000000-0000-4000-8000-000000000099",
  source = "00000000-0000-4000-8000-000000000500";
const signal = () => new AbortController().signal;
const fixture = () =>
  withSyntheticBusinessFacets(
    withSyntheticServerQuery(
      withSyntheticExceptionContext(createDemoGateway()),
    ),
  );
const p = (gateway = fixture()) => ({
  gateway,
  org,
  reviewOnly: false,
  invoice: "",
  onOpen: vi.fn(),
  demo: true,
  refresh: 0,
});
const originalClipboard = Object.getOwnPropertyDescriptor(
  navigator,
  "clipboard",
);
beforeEach(() => window.history.replaceState({}, "", "/demo/anomalies"));
afterEach(() => {
  window.history.replaceState({}, "", "/");
  if (originalClipboard)
    Object.defineProperty(navigator, "clipboard", originalClipboard);
  else Reflect.deleteProperty(navigator, "clipboard");
  vi.restoreAllMocks();
});
function clipboard(writeText = vi.fn().mockResolvedValue(undefined)) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });
  return writeText;
}
function pop(path: string) {
  act(() => {
    window.history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
}
it.each([
  `?ev=1&org=${other}`,
  `?ev=1&org=${org}&token=secret`,
  `?ev=1&org=${org}&ev_q=%FF`,
  `?org=${org}&org=${org}`,
])(
  "blocks before any financial read for inaccessible or invalid link %s",
  async (query) => {
    window.history.replaceState({}, "", "/demo/anomalies" + query);
    const gateway = fixture(),
      load = vi.spyOn(gateway, "load"),
      request = vi.spyOn(gateway, "queryExceptions"),
      labels = vi.spyOn(gateway, "sourceLabel");
    render(
      <ExceptionViewWorkspace
        user={demoUser}
        view="anomalies"
        demo
        gateway={gateway}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No financial search was started",
    );
    expect(load).not.toHaveBeenCalled();
    expect(request).not.toHaveBeenCalled();
    expect(labels).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Open default authorized view" }),
    );
    await screen.findByText("4 matching assessments");
    expect(request).toHaveBeenCalledWith(
      org,
      expect.anything(),
      2,
      null,
      expect.any(AbortSignal),
    );
  },
);
it("restores criteria on refresh/new mount with a new first page and no decisions", async () => {
  const path = viewPath(
    org,
    { currency: "USD", sort: "amount_high" },
    2,
    "anomalies",
    true,
  );
  window.history.replaceState({}, "", path);
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions"),
    decide = vi.spyOn(gateway, "decide");
  const first = render(
    <ExceptionViewWorkspace
      user={demoUser}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  await screen.findByText("3 matching assessments");
  expect(screen.getByLabelText("Server currency")).toHaveValue("USD");
  first.unmount();
  render(
    <ExceptionViewWorkspace
      user={demoUser}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  await screen.findByText("3 matching assessments");
  expect(query.mock.calls.every((c) => c[3] === null)).toBe(true);
  expect(decide).not.toHaveBeenCalled();
});
it("restores Back/Forward criteria and invalidates continuation while preserving investigation position", async () => {
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions");
  render(
    <ExceptionViewWorkspace
      user={demoUser}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  await screen.findByText("4 matching assessments");
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  await screen.findByText(/3–4 of 4/);
  const calls = query.mock.calls.length;
  fireEvent.click(screen.getAllByRole("button", { name: /^Investigate / })[0]);
  await screen.findByRole("button", { name: /Back to anomalies/ });
  fireEvent.click(screen.getByRole("button", { name: /Back to anomalies/ }));
  expect(screen.getByText(/3–4 of 4/)).toBeInTheDocument();
  expect(query).toHaveBeenCalledTimes(calls);
  pop(viewPath(org, { currency: "USD" }, 2, "anomalies", true));
  await screen.findByText("3 matching assessments");
  expect(query).toHaveBeenLastCalledWith(
    org,
    expect.objectContaining({ currency: "USD" }),
    2,
    null,
    expect.any(AbortSignal),
  );
  pop(viewPath(org, {}, 2, "anomalies", true));
  await screen.findByText("4 matching assessments");
  expect(screen.getByLabelText("Server currency")).toHaveValue("");
  expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
});
it("writes acknowledged filters without remounting on pagination and handles clipboard success only after completion", async () => {
  let resolve!: () => void;
  const write = clipboard(
      vi.fn(
        () =>
          new Promise<void>((r) => {
            resolve = r;
          }),
      ),
    ),
    gateway = fixture(),
    decide = vi.spyOn(gateway, "decide");
  render(
    <ExceptionViewWorkspace
      user={demoUser}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  await screen.findByText("4 matching assessments");
  fireEvent.change(screen.getByLabelText("Server sort"), {
    target: { value: "amount_high" },
  });
  await waitFor(() =>
    expect(window.location.search).toContain("ev_sort=amount_high"),
  );
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  await screen.findByText(/3–4 of 4/);
  fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));
  expect(screen.queryByText(/View link copied/)).not.toBeInTheDocument();
  await act(async () => resolve());
  expect(await screen.findByText(/View link copied/)).toBeInTheDocument();
  expect(write.mock.calls[0][0]).toContain("/demo/anomalies?ev=1");
  expect(write.mock.calls[0][0]).not.toMatch(/after|cursor|assessment|token/);
  expect(decide).not.toHaveBeenCalled();
});
it("handles clipboard denial and retries without financial mutation", async () => {
  const write = clipboard(
    vi.fn().mockRejectedValueOnce(Error("denied")).mockResolvedValue(undefined),
  );
  render(
    <ServerExceptionsQueue
      {...p()}
      makeViewLink={() => "https://fixture.test/demo/anomalies"}
    />,
  );
  await screen.findByText("4 matching assessments");
  fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("not copied");
  fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));
  await screen.findByText(/View link copied/);
  expect(write).toHaveBeenCalledTimes(2);
});
it("switches organization with new defaults and aborts old reads", async () => {
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions"),
    user = {
      ...demoUser,
      organizations: [
        ...demoUser.organizations,
        { id: other, name: "Other synthetic", role: "owner" as const },
      ],
    };
  render(
    <ExceptionViewWorkspace
      user={user}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  await screen.findByText("4 matching assessments");
  gateway.load = vi
    .fn()
    .mockImplementation((_, s) => createDemoGateway().load(org, s));
  const oldSignal = query.mock.calls[0][4];
  fireEvent.change(screen.getByLabelText("Active organization"), {
    target: { value: other },
  });
  await waitFor(() => expect(window.location.search).toContain(other));
  expect(oldSignal.aborted).toBe(true);
  await waitFor(() =>
    expect(query).toHaveBeenLastCalledWith(
      other,
      expect.objectContaining({ sort: "newest", needs_review: false }),
      2,
      null,
      expect.any(AbortSignal),
    ),
  );
});
it.each([
  [409, "EXCEPTIONS_CHANGED"],
  [422, "INVALID_EXCEPTIONS_CURSOR"],
] as const)(
  "restarts a typed continuation error once, same criteria, without decision replay (%s)",
  async (status, code) => {
    const gateway = fixture(),
      original = gateway.queryExceptions!,
      query = vi
        .spyOn(gateway, "queryExceptions")
        .mockImplementation(async (...args) => {
          if (args[3]) throw new WorkspaceError("expired", status, null, code);
          return original(...args);
        }),
      decide = vi.spyOn(gateway, "decide");
    render(<ServerExceptionsQueue {...p(gateway)} />);
    await screen.findByText("4 matching assessments");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText(/Restarted at the first page/);
    await screen.findByText(/1–2 of 4/);
    expect(query).toHaveBeenCalledTimes(3);
    expect(query.mock.calls.map((c) => Boolean(c[3]))).toEqual([
      false,
      true,
      false,
    ]);
    expect(decide).not.toHaveBeenCalled();
  },
);
it("never auto-retries a first-page cursor failure or a different conflict", async () => {
  const gateway = fixture(),
    query = vi
      .spyOn(gateway, "queryExceptions")
      .mockRejectedValue(
        new WorkspaceError(
          "bad first page",
          422,
          null,
          "INVALID_EXCEPTIONS_CURSOR",
        ),
      );
  render(<ServerExceptionsQueue {...p(gateway)} />);
  await screen.findByText("bad first page");
  await new Promise((r) => setTimeout(r, 600));
  expect(query).toHaveBeenCalledTimes(1);
  expect(
    cursorNeedsRestart(
      new WorkspaceError("decision conflict", 409, null, "DECISION_CONFLICT"),
    ),
  ).toBe(false);
  expect(cursorNeedsRestart(new Error("network"))).toBe(false);
});
it("restarts only facet pagination for a typed facet change", async () => {
  const gateway = fixture(),
    original = gateway.queryFacets!,
    query = vi
      .spyOn(gateway, "queryFacets")
      .mockImplementation(async (...args) => {
        if (args[5])
          throw new WorkspaceError("changed", 409, null, "FACETS_CHANGED");
        return original(...args);
      });
  render(
    <BusinessFacetSelect
      gateway={gateway}
      org={org}
      filters={{}}
      facet="invoice"
      selected={null}
      onSelect={vi.fn()}
      demo
      refresh={0}
    />,
  );
  fireEvent.focus(screen.getByRole("combobox"));
  await screen.findAllByRole("option");
  fireEvent.click(screen.getByRole("button", { name: "More choices" }));
  await screen.findByText(/Restarted the choices/);
  await screen.findAllByRole("option");
  expect(query).toHaveBeenCalledTimes(3);
});
it("preserves an unavailable selected source, exposes retry and ignores stale label reads", async () => {
  const gateway = fixture(),
    labels = vi
      .spyOn(gateway, "sourceLabel")
      .mockRejectedValue(new WorkspaceError("missing", 404)),
    onSelect = vi.fn();
  const props = {
    gateway,
    org,
    filters: { invoice_source_id: source },
    facet: "invoice" as const,
    selected: null,
    onSelect,
    demo: true,
    refresh: 0,
    id: source,
  };
  const ui = render(<SourceFacetSelect {...props} />);
  await screen.findByRole("button", { name: "Retry invoice label" });
  expect(screen.getByRole("combobox")).toHaveValue(
    "Selected invoice label unavailable",
  );
  expect(onSelect).not.toHaveBeenCalled();
  let finish!: (v: { value: string; label: string }) => void;
  labels.mockImplementation(
    () =>
      new Promise((r) => {
        finish = r;
      }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Retry invoice label" }));
  await waitFor(() => expect(labels).toHaveBeenCalledTimes(2));
  const oldFinish = finish;
  ui.rerender(<SourceFacetSelect {...props} id={other} />);
  await act(async () => oldFinish({ value: source, label: "OLD.pdf" }));
  expect(screen.getByRole("combobox")).not.toHaveValue("OLD.pdf");
});
it("resolves a restored label through two bounded tenant-scoped GETs and rejects cross-org documents", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      Response.json({ id: source, kind: "invoice", document_id: other }),
    )
    .mockResolvedValueOnce(
      Response.json({
        id: other,
        organization_id: org,
        original_filename: "Authorized.pdf",
      }),
    );
  expect(
    await liveWorkspaceGateway.sourceLabel!(org, source, "invoice", signal()),
  ).toMatchObject({ value: source, label: "Authorized.pdf" });
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(
    fetcher.mock.calls.every(
      (c) =>
        String(c[0]).includes(`/organizations/${org}/`) &&
        c[1]?.method === "GET" &&
        !c[1]?.body,
    ),
  ).toBe(true);
  fetcher
    .mockResolvedValueOnce(
      Response.json({ id: source, kind: "invoice", document_id: other }),
    )
    .mockResolvedValueOnce(
      Response.json({
        id: other,
        organization_id: other,
        original_filename: "Hidden.pdf",
      }),
    );
  await expect(
    liveWorkspaceGateway.sourceLabel!(org, source, "invoice", signal()),
  ).rejects.toMatchObject({ status: 404 });
});
it("ignores a late obsolete queue page and acknowledges only the active criteria", async () => {
  const gateway = fixture(),
    original = gateway.queryExceptions!,
    stale = await original(org, {}, 2, null, signal());
  let finish!: (v: typeof stale) => void;
  const query = vi
      .spyOn(gateway, "queryExceptions")
      .mockImplementationOnce(
        () =>
          new Promise((r) => {
            finish = r;
          }),
      )
      .mockImplementation(original),
    onApplied = vi.fn();
  render(<ServerExceptionsQueue {...p(gateway)} onApplied={onApplied} />);
  await waitFor(() => expect(query).toHaveBeenCalledTimes(1));
  const obsolete = query.mock.calls[0][4];
  fireEvent.change(screen.getByLabelText("Server currency"), {
    target: { value: "EUR" },
  });
  await screen.findByText("1 matching assessments");
  expect(obsolete.aborted).toBe(true);
  await act(async () => finish({ ...stale, total: 999 }));
  expect(
    screen.queryByText("999 matching assessments"),
  ).not.toBeInTheDocument();
  expect(onApplied).toHaveBeenCalledTimes(1);
  expect(onApplied).toHaveBeenCalledWith(
    expect.objectContaining({ currency: "EUR" }),
    2,
  );
});
it("does not copy failed/unacknowledged filters and reports an unrepresentable link", async () => {
  const gateway = fixture(),
    query = vi
      .spyOn(gateway, "queryExceptions")
      .mockRejectedValue(Error("unavailable")),
    write = clipboard();
  render(
    <ServerExceptionsQueue
      {...p(gateway)}
      makeViewLink={() => {
        throw Error("length");
      }}
    />,
  );
  await screen.findByText("unavailable");
  expect(screen.getByRole("button", { name: "Copy view link" })).toBeDisabled();
  expect(write).not.toHaveBeenCalled();
  query.mockImplementation(fixture().queryExceptions!);
  fireEvent.click(screen.getByRole("button", { name: "Retry this page" }));
  await screen.findByText("4 matching assessments");
  fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "could not be created",
  );
  expect(write).not.toHaveBeenCalled();
});
it("keeps source IDs for empty results and resolves only authorized labels", async () => {
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions"),
    labels = vi.spyOn(gateway, "sourceLabel");
  window.history.replaceState(
    {},
    "",
    viewPath(
      org,
      { invoice_source_id: source, q: "not present anywhere" },
      2,
      "anomalies",
      true,
    ),
  );
  render(
    <ExceptionViewWorkspace
      user={demoUser}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  await screen.findByText("0 matching assessments");
  expect(screen.getByRole("combobox", { name: "Search invoices" })).toHaveValue(
    "AcmeCloud_INV-2026-1042.pdf",
  );
  expect(labels).toHaveBeenCalledTimes(1);
  expect(query).toHaveBeenLastCalledWith(
    org,
    expect.objectContaining({
      invoice_source_id: source,
      q: "not present anywhere",
    }),
    2,
    null,
    expect.any(AbortSignal),
  );
});
