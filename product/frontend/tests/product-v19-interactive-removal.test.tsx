/** Explicit synthetic/component query boundaries. No authenticated or SQL runtime claim. */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { ServerExceptionsQueue } from "@/components/server-exceptions-queue";
import { ExceptionViewWorkspace } from "@/components/exception-view-workspace";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import { withSyntheticServerQuery } from "@/lib/product-demo-server-query";
import { withSyntheticBusinessFacets } from "@/lib/product-demo-business-facets";
import { WorkspaceError } from "@/lib/product-workspace";
import { readViewSearch, viewPath } from "@/lib/exception-view-url";
import type { ExceptionQuery } from "@/lib/server-exceptions";
const org = demoUser.organizations[0].id,
  other = "00000000-0000-4000-8000-000000000099",
  source = "00000000-0000-4000-8000-000000000500",
  doc = "00000000-0000-4000-8000-000000000101",
  contract = "00000000-0000-4000-8000-000000000505";
const fixture = () =>
  withSyntheticBusinessFacets(
    withSyntheticServerQuery(
      withSyntheticExceptionContext(createDemoGateway()),
    ),
  );
const summary = () =>
  within(screen.getByRole("region", { name: "Applied criteria summary" }));
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
function open(
  filters: ExceptionQuery,
  gateway = fixture(),
  view: "anomalies" | "review" = "anomalies",
) {
  window.history.replaceState({}, "", viewPath(org, filters, 2, view, true));
  return render(
    <ExceptionViewWorkspace
      user={demoUser}
      view={view}
      demo
      gateway={gateway}
    />,
  );
}
async function ready() {
  await waitFor(
    () =>
      expect(
        screen.getByRole("button", { name: "Copy summary & link" }),
      ).toBeEnabled(),
    { timeout: 3000 }, // Allow the initial client mount plus the existing 250 ms query debounce on Cloud.
  );
}
function clip() {
  const write = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: write },
  });
  return write;
}
it.each([
  [
    "Remove supplier filter",
    { supplier: "AcmeCloud", contract_source_id: contract, currency: "USD" },
    "supplier",
  ],
  [
    "Remove contract filter",
    { supplier: "AcmeCloud", contract_source_id: contract },
    "contract_source_id",
  ],
  [
    "Remove invoice filter",
    { invoice_source_id: source, invoice_document_id: doc },
    "invoice_source_id",
  ],
  [
    "Remove invoice document filter",
    { invoice_source_id: source, invoice_document_id: doc },
    "invoice_document_id",
  ],
  ["Remove currency filter", { currency: "USD" }, "currency"],
  ["Remove search filter", { q: "Enterprise", currency: "USD" }, "q"],
  [
    "Remove created from filter",
    {
      created_from: "2026-10-01T00:00:00Z",
      created_to: "2026-11-01T00:00:00Z",
    },
    "created_from",
  ],
  [
    "Remove created before filter",
    {
      created_from: "2026-10-01T00:00:00Z",
      created_to: "2026-11-01T00:00:00Z",
    },
    "created_to",
  ],
  ["Remove current assessments filter", { current: true }, "current"],
  ["Remove needs review filter", { needs_review: true }, "needs_review"],
  [
    "Remove missing contract filter",
    { missing_contract: true },
    "missing_contract",
  ],
  ["Remove outcome filter", { outcome: "POTENTIAL_LEAKAGE" }, "outcome"],
  [
    "Remove decision status filter",
    { decision_status: "unrecorded" },
    "decision_status",
  ],
] as [string, ExceptionQuery, keyof ExceptionQuery][])(
  "%s uses a fresh bounded read and preserves independent criteria",
  async (name, filters, field) => {
    const gateway = fixture(),
      query = vi.spyOn(gateway, "queryExceptions"),
      decide = vi.spyOn(gateway, "decide");
    open(filters, gateway);
    await ready();
    const before = query.mock.calls.at(-1)![1];
    fireEvent.click(screen.getByRole("button", { name }));
    expect(
      screen.getByRole("heading", { name: "Applied criteria" }),
    ).toHaveFocus();
    expect(
      screen.getByRole("button", { name: "Copy view link" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Copy summary & link" }),
    ).toBeDisabled();
    await ready();
    const last = query.mock.calls.at(-1)!;
    expect(last[0]).toBe(org);
    expect(last[2]).toBe(2);
    expect(last[3]).toBeNull();
    expect(last[1][field]).toBe(field === "needs_review" ? false : undefined);
    for (const [k, v] of Object.entries(before))
      if (k !== field) expect(last[1][k as keyof ExceptionQuery]).toEqual(v);
    expect(query).toHaveBeenCalledTimes(2);
    expect(decide).not.toHaveBeenCalled();
    expect(summary().queryByRole("button", { name })).not.toBeInTheDocument();
    expect(summary().getByRole("status")).toHaveTextContent(
      "Server results refreshed",
    );
  },
);
it("does not remove implicit review restriction and restores its explicit false override", async () => {
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions");
  const ui = open({ needs_review: false, currency: "USD" }, gateway, "review");
  await ready();
  fireEvent.click(
    screen.getByRole("button", { name: "Restore default needs review filter" }),
  );
  await ready();
  expect(query.mock.calls.at(-1)![1]).toMatchObject({
    needs_review: true,
    currency: "USD",
  });
  expect(window.location.search).not.toContain("ev_needs_review");
  expect(
    screen.queryByRole("button", {
      name: /Remove needs review|Restore default needs review/,
    }),
  ).not.toBeInTheDocument();
  ui.unmount();
});
it("resets page-two navigation and never reuses its cursor after removal", async () => {
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions");
  open({ currency: "USD" }, gateway);
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  await screen.findByText(/3–3 of 3/);
  expect(query.mock.calls.at(-1)![3]).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: "Remove currency filter" }),
  );
  await ready();
  expect(query.mock.calls.at(-1)![3]).toBeNull();
  expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
  expect(screen.getByText(/1–2 of 4/)).toBeInTheDocument();
});
it("serializes rapid removals, ignores a canceled result, and keeps the authoritative URL until success", async () => {
  const gateway = fixture(),
    original = gateway.queryExceptions!,
    query = vi.spyOn(gateway, "queryExceptions");
  open({ supplier: "AcmeCloud", currency: "USD" }, gateway);
  await ready();
  const oldUrl = window.location.href;
  let finish!: (v: Awaited<ReturnType<typeof original>>) => void;
  query.mockImplementationOnce(
    () =>
      new Promise((r) => {
        finish = r;
      }),
  );
  const b = screen.getByRole("button", { name: "Remove supplier filter" });
  act(() => {
    fireEvent.click(b);
    fireEvent.click(b);
    fireEvent.click(
      screen.getByRole("button", { name: "Remove currency filter" }),
    );
  });
  await waitFor(() => expect(query).toHaveBeenCalledTimes(2));
  expect(window.location.href).toBe(oldUrl);
  expect(summary().getByText("AcmeCloud", { exact: true })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Server currency"), {
    target: { value: "EUR" },
  });
  await ready();
  expect(query).toHaveBeenCalledTimes(3);
  const latest = window.location.href;
  await act(async () =>
    finish(
      await original(
        org,
        { currency: "USD" },
        2,
        null,
        new AbortController().signal,
      ),
    ),
  );
  expect(window.location.href).toBe(latest);
  expect(summary().getByText("EUR", { exact: true })).toBeInTheDocument();
  expect(summary().queryByText("USD", { exact: true })).not.toBeInTheDocument();
});
it("retains failed removal snapshot and URL, blocks copy and removals, and restores applied criteria explicitly", async () => {
  const gateway = fixture(),
    original = gateway.queryExceptions!,
    query = vi.spyOn(gateway, "queryExceptions");
  open({ supplier: "AcmeCloud", currency: "USD" }, gateway);
  await ready();
  const oldUrl = window.location.href;
  query.mockRejectedValueOnce(Error("read unavailable"));
  fireEvent.click(
    screen.getByRole("button", { name: "Remove supplier filter" }),
  );
  await screen.findByText("read unavailable");
  expect(summary().getByRole("alert")).toHaveTextContent(
    "Requested change failed",
  );
  expect(summary().getByText("AcmeCloud", { exact: true })).toBeInTheDocument();
  expect(window.location.href).toBe(oldUrl);
  expect(
    screen.getByRole("button", { name: "Copy summary & link" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Remove currency filter" }),
  ).toBeDisabled();
  query.mockImplementation(original);
  fireEvent.click(
    screen.getByRole("button", { name: "Restore last applied criteria" }),
  );
  await ready();
  expect(query.mock.calls.at(-1)![1].supplier).toBe("AcmeCloud");
  expect(window.location.href).toBe(oldUrl);
  expect(query).toHaveBeenCalledTimes(3);
});
it("retries a failed requested read once by explicit action, then copies the new snapshot and matching URL", async () => {
  const write = clip(),
    gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions");
  open({ supplier: "AcmeCloud", currency: "USD" }, gateway);
  await ready();
  query.mockRejectedValueOnce(Error("read unavailable"));
  fireEvent.click(
    screen.getByRole("button", { name: "Remove supplier filter" }),
  );
  await screen.findByText("read unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Retry this page" }));
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Copy summary & link" }));
  await waitFor(() => expect(write).toHaveBeenCalled());
  const text = write.mock.calls[0][0] as string,
    link = text.split("View link: ")[1].split("\n")[0];
  expect(text).not.toMatch(
    /Recorded supplier name:|9,600|9600\.000000|matching assessments|reason:|citations:/,
  );
  expect(
    readViewSearch(new URL(link).search, "anomalies", true).filters.supplier,
  ).toBeUndefined();
  expect(text).toContain("Currency filter: USD");
  fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));
  await waitFor(() => expect(write).toHaveBeenCalledTimes(2));
  expect(write.mock.calls[1][0]).toBe(link);
  expect(query).toHaveBeenCalledTimes(3);
});
it("restores removed criteria on Back and reapplies their removal on Forward", async () => {
  open({ currency: "USD" });
  await ready();
  const old = window.location.pathname + window.location.search;
  fireEvent.click(
    screen.getByRole("button", { name: "Remove currency filter" }),
  );
  await ready();
  const next = window.location.pathname + window.location.search;
  for (const [path, present] of [
    [old, true],
    [next, false],
  ] as const) {
    act(() => {
      window.history.pushState({}, "", path);
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await ready();
    expect(
      Boolean(screen.queryByRole("button", { name: "Remove currency filter" })),
    ).toBe(present);
    expect(
      screen.getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
  }
});
it("keeps an unavailable ambiguous source removable without selecting an approved replacement", async () => {
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions");
  open({ contract_source_id: other, supplier: "AcmeCloud" }, gateway);
  await ready();
  expect(
    summary().getByText("Selected contract label unavailable"),
  ).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: "Remove contract filter" }),
  );
  await ready();
  expect(query.mock.calls.at(-1)![1]).toMatchObject({ supplier: "AcmeCloud" });
  expect(query.mock.calls.at(-1)![1].contract_source_id).toBeUndefined();
});
it("blocks actions when authorization is withdrawn and never offers organization/order/page removal", async () => {
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions");
  const props = {
    gateway,
    org,
    organization: "Synthetic org",
    invoice: "",
    reviewOnly: false,
    demo: true,
    onOpen: vi.fn(),
    refresh: 0,
    initialFilters: { currency: "USD" },
    makeViewLink: (f: ExceptionQuery, l: number) =>
      "https://fixture.test" + viewPath(org, f, l, "anomalies", true),
  };
  const ui = render(<ServerExceptionsQueue {...props} criteriaAuthorized />);
  await ready();
  ui.rerender(<ServerExceptionsQueue {...props} criteriaAuthorized={false} />);
  expect(
    screen.getByRole("button", { name: "Remove currency filter" }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Remove currency filter" }),
  );
  expect(query).toHaveBeenCalledTimes(1);
  expect(
    screen.queryByRole("button", {
      name: /Remove organization|Remove sort|Remove page/,
    }),
  ).not.toBeInTheDocument();
});
it("handles typed expired cursors after a successful removal without replaying decisions", async () => {
  const gateway = fixture(),
    original = gateway.queryExceptions!,
    decide = vi.spyOn(gateway, "decide"),
    query = vi
      .spyOn(gateway, "queryExceptions")
      .mockImplementation(async (...args) => {
        if (args[3])
          throw new WorkspaceError(
            "expired",
            422,
            null,
            "INVALID_EXCEPTIONS_CURSOR",
          );
        return original(...args);
      });
  open({ supplier: "AcmeCloud" }, gateway);
  await ready();
  fireEvent.click(
    screen.getByRole("button", { name: "Remove supplier filter" }),
  );
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  await screen.findByText(/Restarted at the first page/);
  await ready();
  expect(query.mock.calls.at(-1)![3]).toBeNull();
  expect(query).toHaveBeenCalledTimes(4);
  expect(decide).not.toHaveBeenCalled();
});

it("does not report an acknowledged removal as failed when a later page read fails", async () => {
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions");
  open({ supplier: "AcmeCloud" }, gateway);
  await ready();
  fireEvent.click(
    screen.getByRole("button", { name: "Remove supplier filter" }),
  );
  await ready();
  const url = window.location.href;
  query.mockRejectedValueOnce(Error("later page unavailable"));
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  await screen.findByText("later page unavailable");
  expect(summary().getByRole("status")).toHaveTextContent(
    "Supplier filter removed",
  );
  expect(
    summary().queryByText(/Requested change failed/),
  ).not.toBeInTheDocument();
  expect(window.location.href).toBe(url);
  expect(
    screen.getByRole("button", { name: "Copy summary & link" }),
  ).toBeDisabled();
});
it("aborts a pending removal when switching authorized organizations and ignores its late response", async () => {
  const gateway = fixture(),
    originalLoad = gateway.load,
    originalQuery = gateway.queryExceptions!;
  const data = await originalQuery(
    org,
    {},
    2,
    null,
    new AbortController().signal,
  );
  const query = vi.spyOn(gateway, "queryExceptions");
  const load = vi
    .spyOn(gateway, "load")
    .mockImplementation((tenant, s) =>
      tenant === org ? originalLoad(tenant, s) : new Promise(() => {}),
    );
  const user = {
    ...demoUser,
    organizations: [
      ...demoUser.organizations,
      {
        id: other,
        name: "Other synthetic organization",
        role: "owner" as const,
      },
    ],
  };
  window.history.replaceState(
    {},
    "",
    viewPath(org, { supplier: "AcmeCloud" }, 2, "anomalies", true),
  );
  render(
    <ExceptionViewWorkspace
      user={user}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  await ready();
  let finish!: (v: typeof data) => void;
  query.mockImplementationOnce(
    () =>
      new Promise((r) => {
        finish = r;
      }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Remove supplier filter" }),
  );
  await waitFor(() => expect(query).toHaveBeenCalledTimes(2));
  const pendingSignal = query.mock.calls.at(-1)![4];
  fireEvent.change(screen.getByLabelText("Active organization"), {
    target: { value: other },
  });
  await waitFor(() => expect(window.location.search).toContain(other));
  expect(pendingSignal.aborted).toBe(true);
  await act(async () => finish(data));
  expect(
    screen.queryByRole("region", { name: "Applied criteria summary" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByText(/Supplier filter removed/)).not.toBeInTheDocument();
  expect(load).toHaveBeenLastCalledWith(other, expect.any(AbortSignal));
  expect(window.location.search).not.toContain("supplier");
});
it("keeps later-page position when investigating after a successful removal", async () => {
  const gateway = fixture(),
    query = vi.spyOn(gateway, "queryExceptions");
  open({ currency: "USD" }, gateway);
  await ready();
  fireEvent.click(
    screen.getByRole("button", { name: "Remove currency filter" }),
  );
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  await screen.findByText(/3–4 of 4/);
  const count = query.mock.calls.length;
  fireEvent.click(screen.getAllByRole("button", { name: /^Investigate / })[0]);
  fireEvent.click(
    await screen.findByRole("button", { name: /Back to anomalies/ }),
  );
  expect(screen.getByText(/3–4 of 4/)).toBeInTheDocument();
  expect(query).toHaveBeenCalledTimes(count);
  expect(
    summary().queryByRole("button", { name: "Remove currency filter" }),
  ).not.toBeInTheDocument();
});
