/** Explicit memory/transport doubles. No native OIDC/PostgreSQL claim. */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PersonalSavedViews } from "@/components/personal-saved-views";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticSavedViews } from "@/lib/product-demo-saved-views";
import {
  savedDefinition,
  SavedViewsError,
  type SavedView,
} from "@/lib/saved-views";
const org = demoUser.organizations[0].id,
  owner = demoUser.id,
  name = "CFO monthly review";
const def = (currency = "USD") =>
  savedDefinition({
    view_type: "anomalies",
    format_version: 1,
    criteria: { currency },
    page_size: 20,
  });
const signal = () => new AbortController().signal;
const panel = () =>
  within(screen.getByRole("region", { name: "My saved views" }));
const summary = () =>
  within(screen.getByRole("region", { name: "Saved view reconciliation" }));
const review = () =>
  within(screen.getByRole("region", { name: "Review saved view rename" }));
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});
async function setup() {
  const gateway = withSyntheticSavedViews(
    createDemoGateway(),
    false,
  ).savedViews!;
  const row = await gateway.create(
    org,
    owner,
    "CFO watchlist",
    def(),
    signal(),
  );
  const originalUpdate = gateway.update.bind(gateway),
    originalGet = gateway.get.bind(gateway);
  const update = vi.spyOn(gateway, "update"),
    get = vi.spyOn(gateway, "get"),
    remove = vi.spyOn(gateway, "remove");
  const props = {
    gateway,
    org,
    owner,
    view: "anomalies" as const,
    demo: true,
    authorized: true,
    canSave: true,
    getCurrent: () => def(),
    onOpen: vi.fn(() => true),
  };
  const rendered = render(<PersonalSavedViews {...props} />);
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Manage saved view CFO watchlist",
    }),
  );
  await screen.findByRole("textbox", { name: "Rename personal view" });
  get.mockClear();
  return {
    gateway,
    row,
    originalUpdate,
    originalGet,
    update,
    get,
    remove,
    props,
    rendered,
  };
}
type Setup = Awaited<ReturnType<typeof setup>>;
function draft(value = name) {
  fireEvent.change(
    panel().getByRole("textbox", { name: "Rename personal view" }),
    { target: { value } },
  );
}
async function lose(
  f: Setup,
  recorded = true,
  error: Error = new TypeError("Synthetic rename response lost"),
) {
  f.update.mockImplementationOnce(async (...args) => {
    if (recorded) await f.originalUpdate(...args);
    throw error;
  });
  draft();
  fireEvent.click(panel().getByRole("button", { name: "Rename view" }));
  await screen.findByRole("region", { name: "Saved view reconciliation" });
}
async function check() {
  fireEvent.click(
    summary().getByRole("button", { name: "Check rename state" }),
  );
  await waitFor(() =>
    expect(
      summary().getByRole("button", { name: "Check rename state" }),
    ).toBeEnabled(),
  );
}
async function freshReview() {
  fireEvent.click(
    summary().getByRole("button", { name: "Review rename again" }),
  );
  await screen.findByRole("region", { name: "Review saved view rename" });
  await waitFor(() =>
    expect(
      panel().getByRole("textbox", { name: "Rename personal view" }),
    ).toBeEnabled(),
  );
}
it("captures the name-only payload and exposes uncertain rename without automatic read or replay", async () => {
  const f = await setup();
  await lose(f);
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(f.get).not.toHaveBeenCalled();
  expect(f.update.mock.calls[0].slice(0, 5)).toEqual([
    org,
    owner,
    f.row.id,
    1,
    { name },
  ]);
  expect(summary().getByText("Rename saved view")).toBeInTheDocument();
  expect(
    summary().getByText(/UI correlation only; not a server transaction ID/),
  ).toBeInTheDocument();
  expect(summary().getByRole("heading")).toHaveFocus();
  expect(
    screen.queryByText("Synthetic view renamed in memory only."),
  ).not.toBeInTheDocument();
});
it("observes the proposed name after one authorized GET without attributing the transaction", async () => {
  const f = await setup();
  await lose(f);
  await check();
  expect(f.get).toHaveBeenLastCalledWith(
    org,
    owner,
    f.row.id,
    expect.any(AbortSignal),
  );
  expect(
    summary().getByText("Proposed name found in the saved view."),
  ).toBeInTheDocument();
  expect(
    summary().getByText(/Saved criteria remain unchanged/),
  ).toBeInTheDocument();
  expect(
    summary().getByText(/does not prove that this particular attempt/),
  ).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("observes the old name at original revision without claiming definitive write failure", async () => {
  const f = await setup();
  await lose(f, false, new DOMException("Synthetic timeout", "TimeoutError"));
  await check();
  expect(
    summary().getByText(
      "Previous name is still recorded as of the latest read.",
    ),
  ).toBeInTheDocument();
  expect(
    summary().getByText(/not proof that the write failed/),
  ).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("does not mistake a matching new name plus changed criteria for a coherent rename", async () => {
  const f = await setup();
  await lose(f);
  await f.originalUpdate(
    org,
    owner,
    f.row.id,
    2,
    { definition: def("EUR") },
    signal(),
  );
  await check();
  expect(
    summary().getByText("The saved view differs from both compared states."),
  ).toBeInTheDocument();
  expect(
    summary().getByText(/Saved criteria have changed/),
  ).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("requires a fresh name review and new explicit confirmation, preserving concurrently changed criteria", async () => {
  const f = await setup();
  await lose(f, false);
  await f.originalUpdate(
    org,
    owner,
    f.row.id,
    1,
    { definition: def("EUR") },
    signal(),
  );
  await check();
  draft("Revised draft");
  await freshReview();
  expect(review().getByText(/Re-read version 2/)).toBeInTheDocument();
  expect(review().getByRole("heading")).toHaveFocus();
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(panel().getByRole("button", { name: "Rename view" })).toBeDisabled();
  fireEvent.click(review().getByRole("button", { name: "Confirm rename" }));
  await screen.findByText("Synthetic view renamed in memory only.");
  expect(f.update).toHaveBeenCalledTimes(2);
  expect(f.update.mock.calls[1].slice(0, 5)).toEqual([
    org,
    owner,
    f.row.id,
    2,
    { name: "Revised draft" },
  ]);
  expect(
    (await f.originalGet(org, owner, f.row.id, signal())).criteria.currency,
  ).toBe("EUR");
});
it("finds no new name change after a recorded rename and never sends a second PATCH", async () => {
  const f = await setup();
  await lose(f);
  await check();
  await freshReview();
  expect(review().getByText("No name changes to save")).toBeInTheDocument();
  expect(
    review().getByRole("button", { name: "Confirm rename" }),
  ).toBeDisabled();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it.each(["CFO watchlist", " ＣＦＯ   watchlist "])(
  "refuses effective no-op rename %s",
  async (value) => {
    const f = await setup();
    draft(value);
    fireEvent.click(panel().getByRole("button", { name: "Rename view" }));
    await screen.findByText("No name changes to save");
    expect(f.update).not.toHaveBeenCalled();
  },
);
it("normalizes Unicode and whitespace before sending a name-only PATCH", async () => {
  const f = await setup();
  draft(" ＣＦＯ   monthly review ");
  fireEvent.click(panel().getByRole("button", { name: "Rename view" }));
  await screen.findByText("Synthetic view renamed in memory only.");
  expect(f.update.mock.calls[0][4]).toEqual({ name });
});
it("retains the name draft on a real synthetic name collision and does not retry", async () => {
  const f = await setup();
  await f.gateway.create(org, owner, name, def(), signal());
  await lose(f);
  expect(
    summary().getByText(/rename request returned a conflict/),
  ).toBeInTheDocument();
  expect(
    panel().getByRole("textbox", { name: "Rename personal view" }),
  ).toHaveValue(name);
  await check();
  expect(
    summary().getByText(
      "Previous name is still recorded as of the latest read.",
    ),
  ).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("fences a concurrent change between fresh review and explicit rename confirmation with HTTP 409", async () => {
  const f = await setup();
  await lose(f, false);
  await check();
  await freshReview();
  await f.originalUpdate(
    org,
    owner,
    f.row.id,
    1,
    { definition: def("EUR") },
    signal(),
  );
  fireEvent.click(review().getByRole("button", { name: "Confirm rename" }));
  await screen.findByRole("region", { name: "Saved view reconciliation" });
  expect(summary().getByText(/returned a conflict/)).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(2);
  expect((await f.originalGet(org, owner, f.row.id, signal())).name).toBe(
    f.row.name,
  );
});
it("invalidates the reviewed name on edit, even if the user restores the previous draft", async () => {
  const f = await setup();
  await lose(f, false);
  await check();
  await freshReview();
  draft("Temporary");
  draft(name);
  expect(
    screen.queryByRole("region", { name: "Review saved view rename" }),
  ).not.toBeInTheDocument();
  fireEvent.click(panel().getByRole("button", { name: "Rename view" }));
  await screen.findByRole("region", { name: "Review saved view rename" });
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("cancels the fresh rename review without mutation and returns focus", async () => {
  const f = await setup();
  await lose(f, false);
  await check();
  await freshReview();
  fireEvent.click(
    review().getByRole("button", { name: "Cancel rename review" }),
  );
  expect(
    panel().getByRole("heading", { name: "My saved views" }),
  ).toHaveFocus();
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(f.remove).not.toHaveBeenCalled();
});
it.each([503, 404])(
  "keeps unknown outcome on read HTTP %s and recovers only after another read",
  async (status) => {
    const f = await setup();
    await lose(f);
    f.get.mockRejectedValueOnce(
      new SavedViewsError("Sensitive upstream detail", status),
    );
    await check();
    expect(
      summary().getByText("Unable to determine the saved state."),
    ).toBeInTheDocument();
    expect(
      summary().getByRole("button", { name: "Review rename again" }),
    ).toBeDisabled();
    expect(
      screen.queryByText(/Sensitive upstream detail/),
    ).not.toBeInTheDocument();
    await check();
    expect(
      summary().getByText("Proposed name found in the saved view."),
    ).toBeInTheDocument();
    expect(f.update).toHaveBeenCalledTimes(1);
  },
);
it.each([401, 403])(
  "clears names and private attempt state on read HTTP %s",
  async (status) => {
    const f = await setup();
    await lose(f);
    f.get.mockRejectedValueOnce(
      new SavedViewsError("Private foreign name", status),
    );
    fireEvent.click(
      summary().getByRole("button", { name: "Check rename state" }),
    );
    await screen.findByText(/private view context cleared/);
    expect(
      panel().queryByText(
        /CFO watchlist|CFO monthly review|Private foreign name/,
      ),
    ).not.toBeInTheDocument();
    expect(
      panel().getByRole("button", { name: "Reload personal views" }),
    ).toBeDisabled();
  },
);
it.each(["org", "owner", "membership"])(
  "discards the attempt and ignores late replies after %s changes",
  async (scope) => {
    const f = await setup();
    await lose(f);
    let release!: (r: SavedView) => void, oldSignal!: AbortSignal;
    f.get.mockImplementationOnce((_o, _u, _id, s) => {
      oldSignal = s;
      return new Promise((r) => {
        release = r;
      });
    });
    fireEvent.click(
      summary().getByRole("button", { name: "Check rename state" }),
    );
    const props = {
      ...f.props,
      ...(scope === "org"
        ? { org: "bbbbbbbb-0000-4000-8000-000000000001" }
        : scope === "owner"
          ? { owner: "bbbbbbbb-0000-4000-8000-000000000001" }
          : { authorized: false }),
    };
    f.rendered.rerender(<PersonalSavedViews {...props} />);
    expect(oldSignal.aborted).toBe(true);
    await act(async () => release({ ...f.row, name, revision: 2 }));
    expect(
      screen.queryByRole("region", { name: "Saved view reconciliation" }),
    ).not.toBeInTheDocument();
    expect(
      panel().queryByText(/CFO watchlist|CFO monthly review|local-1/),
    ).not.toBeInTheDocument();
  },
);
it("rejects a homonymous view with another ID without revealing its name or accepting state", async () => {
  const f = await setup();
  await lose(f);
  f.get.mockResolvedValueOnce({
    ...f.row,
    id: "bbbbbbbb-0000-4000-8000-000000000001",
    name,
    revision: 2,
  });
  await check();
  expect(
    summary().getByText("Unable to determine the saved state."),
  ).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("ignores an obsolete read after closing and a subsequent fresh read", async () => {
  const f = await setup();
  await lose(f);
  let late!: (r: SavedView) => void;
  f.get.mockImplementationOnce(
    () =>
      new Promise((r) => {
        late = r;
      }),
  );
  fireEvent.click(
    summary().getByRole("button", { name: "Check rename state" }),
  );
  fireEvent.click(summary().getByRole("button", { name: "Close summary" }));
  expect(
    panel().getByRole("heading", { name: "My saved views" }),
  ).toHaveFocus();
  fireEvent.click(panel().getByRole("button", { name: "Check rename state" }));
  await screen.findByText("Proposed name found in the saved view.");
  await act(async () => late({ ...f.row, revision: 10 }));
  expect(summary().getByText(/Observed version 2/)).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("bounds a hung read at 30 seconds, supports a new read and ignores its late response", async () => {
  const f = await setup();
  await lose(f);
  let late!: (r: SavedView) => void;
  f.get.mockImplementationOnce(
    () =>
      new Promise((r) => {
        late = r;
      }),
  );
  vi.useFakeTimers();
  fireEvent.click(
    summary().getByRole("button", { name: "Check rename state" }),
  );
  await act(async () => {
    vi.advanceTimersByTime(30000);
  });
  expect(summary().getByText(/timed out/)).toBeInTheDocument();
  vi.useRealTimers();
  await check();
  await act(async () => late({ ...f.row, revision: 1 }));
  expect(
    summary().getByText("Proposed name found in the saved view."),
  ).toBeInTheDocument();
});
it("guards rapid double rename clicks and waits for acknowledgment without issuing another PATCH", async () => {
  const f = await setup();
  let release!: () => void;
  f.update.mockImplementationOnce(async (...args) => {
    await f.originalUpdate(...args);
    await new Promise<void>((r) => {
      release = r;
    });
    throw new TypeError("Synthetic lost response");
  });
  draft();
  const button = panel().getByRole("button", {
    name: "Rename view",
  });
  act(() => {
    fireEvent.click(button);
    fireEvent.click(button);
  });
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(
    screen.queryByText("Synthetic view renamed in memory only."),
  ).not.toBeInTheDocument();
  await waitFor(() => expect(release).toBeTypeOf("function"));
  await act(async () => release());
  await check();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it.each(["name", "criteria", "revision"])(
  "does not acknowledge a response with mismatched %s",
  async (field) => {
    const f = await setup();
    const row = Object.assign(
      { ...f.row, name, revision: 2 },
      field === "name"
        ? { name: "Unexpected" }
        : field === "criteria"
          ? { criteria: { currency: "EUR" } }
          : { revision: 3 },
    );
    f.update.mockResolvedValueOnce(row);
    draft();
    fireEvent.click(panel().getByRole("button", { name: "Rename view" }));
    await screen.findByRole("region", { name: "Saved view reconciliation" });
    expect(
      screen.queryByText("Synthetic view renamed in memory only."),
    ).not.toBeInTheDocument();
    expect(f.update).toHaveBeenCalledTimes(1);
  },
);
it("keeps rename review independent from financial query readiness and loses context honestly on remount", async () => {
  const f = await setup();
  await lose(f, false);
  f.rendered.rerender(<PersonalSavedViews {...f.props} canSave={false} />);
  await check();
  await freshReview();
  expect(
    review().getByRole("button", { name: "Confirm rename" }),
  ).toBeEnabled();
  f.rendered.unmount();
  render(<PersonalSavedViews {...f.props} />);
  expect(
    panel().getByText(
      /After a page reload, attribution of a prior operation is unavailable/,
    ),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("region", { name: "Saved view reconciliation" }),
  ).not.toBeInTheDocument();
});
it("keeps raw IDs, financial data, credentials and transaction-success claims out of the rename summary", async () => {
  const f = await setup();
  await lose(f);
  await check();
  const text = screen.getByRole("region", {
    name: "Saved view reconciliation",
  }).textContent;
  expect(text).not.toMatch(
    new RegExp(
      `${f.row.id}|${owner}|${org}|1,380|Bearer|after=|Rename successful|Successfully saved`,
    ),
  );
  expect(f.remove).not.toHaveBeenCalled();
});
