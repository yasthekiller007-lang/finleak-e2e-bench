/** Explicit component/API fixtures; not authenticated OIDC/PostgreSQL proof. */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ExceptionViewWorkspace } from "@/components/exception-view-workspace";
import { AppliedCriteriaSummary } from "@/components/applied-criteria-summary";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import { withSyntheticServerQuery } from "@/lib/product-demo-server-query";
import { withSyntheticBusinessFacets } from "@/lib/product-demo-business-facets";
import { readViewSearch, viewPath } from "@/lib/exception-view-url";
const org = demoUser.organizations[0].id,
  source = "00000000-0000-4000-8000-000000000500",
  other = "00000000-0000-4000-8000-000000000099";
const fixture = () =>
  withSyntheticBusinessFacets(
    withSyntheticServerQuery(
      withSyntheticExceptionContext(createDemoGateway()),
    ),
  );
const summary = () =>
  within(screen.getByRole("region", { name: "Applied criteria summary" }));
const copyButton = () =>
  screen.getByRole("button", { name: "Copy summary & link" });
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
function open(gateway = fixture()) {
  return render(
    <ExceptionViewWorkspace
      user={demoUser}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
}
it("shows loading, then applied defaults without copying automatically or leaking amounts", async () => {
  const write = clipboard();
  open();
  await screen.findByRole("region", { name: "Applied criteria summary" });
  expect(
    await summary().findByText("Waiting for the first successful query."),
  ).toBeInTheDocument();
  expect(copyButton()).toBeDisabled();
  await screen.findByText("4 matching assessments");
  expect(
    summary().getByText("No optional filters selected."),
  ).toBeInTheDocument();
  expect(summary().getByText("Northstar Industries")).toBeInTheDocument();
  expect(summary().queryByText(/9,600|2,880|1,380/)).not.toBeInTheDocument();
  expect(write).not.toHaveBeenCalled();
});
it("copies a coherent applied summary and exactly the V17 link, preserving its separate button", async () => {
  const write = clipboard(),
    gateway = fixture(),
    decide = vi.spyOn(gateway, "decide");
  open(gateway);
  await screen.findByText("4 matching assessments");
  fireEvent.change(screen.getByLabelText("Server currency"), {
    target: { value: "EUR" },
  });
  await screen.findByText("1 matching assessments");
  fireEvent.click(copyButton());
  await summary().findByText(/Summary and view link copied/);
  const copied = write.mock.calls[0][0] as string,
    url = copied.split("View link: ")[1].split("\n")[0];
  expect(copied).toContain("Currency filter: EUR");
  expect(copied).not.toMatch(
    /1,380|1380\.000000|matching assessments|scope_key|actor_id/,
  );
  expect(
    readViewSearch(new URL(url).search, "anomalies", true).filters.currency,
  ).toBe("EUR");
  fireEvent.click(screen.getByRole("button", { name: "Copy view link" }));
  await screen.findByText("View link copied. Permissions are unchanged.");
  expect(write.mock.calls[1][0]).toBe(url);
  expect(decide).not.toHaveBeenCalled();
});
it("keeps the successful summary during a changed draft, error and retry", async () => {
  const gateway = fixture(),
    original = gateway.queryExceptions!,
    query = vi.spyOn(gateway, "queryExceptions");
  open(gateway);
  await screen.findByText("4 matching assessments");
  query.mockRejectedValueOnce(Error("read failed"));
  fireEvent.change(screen.getByLabelText("Server currency"), {
    target: { value: "USD" },
  });
  expect(copyButton()).toBeDisabled();
  expect(
    summary().getByText(/Criteria changed or a read is pending/),
  ).toBeInTheDocument();
  expect(summary().queryByText("USD", { exact: true })).not.toBeInTheDocument();
  await screen.findByText("read failed");
  expect(
    summary().getByText(/Query failed. Showing the last successful criteria/),
  ).toBeInTheDocument();
  expect(copyButton()).toBeDisabled();
  query.mockImplementation(original);
  fireEvent.click(screen.getByRole("button", { name: "Retry this page" }));
  await screen.findByText("3 matching assessments");
  expect(summary().getByText("USD", { exact: true })).toBeInTheDocument();
  expect(copyButton()).toBeEnabled();
});
it("ignores an obsolete response while applying and copying the newer criteria", async () => {
  const gateway = fixture(),
    original = gateway.queryExceptions!,
    old = await original(org, {}, 2, null, new AbortController().signal);
  let finish!: (v: typeof old) => void;
  vi.spyOn(gateway, "queryExceptions")
    .mockImplementationOnce(
      () =>
        new Promise((r) => {
          finish = r;
        }),
    )
    .mockImplementation(original);
  const write = clipboard();
  open(gateway);
  await waitFor(() => expect(finish).toBeDefined());
  fireEvent.change(screen.getByLabelText("Server currency"), {
    target: { value: "EUR" },
  });
  await screen.findByText("1 matching assessments");
  await act(async () => finish(old));
  fireEvent.click(copyButton());
  await waitFor(() => expect(write).toHaveBeenCalled());
  expect(write.mock.calls[0][0]).toContain("Currency filter: EUR");
});
it("restores labels using existing selector reads without extra summary requests", async () => {
  window.history.replaceState(
    {},
    "",
    viewPath(
      org,
      { invoice_source_id: source, supplier: "AcmeCloud", currency: "USD" },
      2,
      "anomalies",
      true,
    ),
  );
  const gateway = fixture(),
    labels = vi.spyOn(gateway, "sourceLabel");
  open(gateway);
  await screen.findByText("1 matching assessments");
  await summary().findByText("AcmeCloud_INV-2026-1042.pdf", { exact: true });
  expect(labels).toHaveBeenCalledTimes(1);
  expect(summary().getByText("AcmeCloud", { exact: true })).toBeInTheDocument();
});
it("keeps an unavailable source as a neutral label without copying its ID as a name", async () => {
  window.history.replaceState(
    {},
    "",
    viewPath(org, { invoice_source_id: other }, 2, "anomalies", true),
  );
  const write = clipboard();
  open();
  await screen.findByText("0 matching assessments");
  expect(
    summary().getByText("Selected invoice label unavailable"),
  ).toBeInTheDocument();
  fireEvent.click(copyButton());
  await waitFor(() => expect(write).toHaveBeenCalled());
  expect(write.mock.calls[0][0]).toContain(
    "Invoice source document: Selected invoice label unavailable",
  );
  expect(write.mock.calls[0][0]).not.toContain(
    "Invoice source document: " + other,
  );
});
it("keeps applied criteria through pagination and restores summary on Back/Forward", async () => {
  const gateway = fixture();
  open(gateway);
  await screen.findByText("4 matching assessments");
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  await screen.findByText(/3–4 of 4/);
  expect(summary().getByText("2", { exact: true })).toBeInTheDocument();
  act(() => {
    window.history.pushState(
      {},
      "",
      viewPath(org, { currency: "USD" }, 2, "anomalies", true),
    );
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await screen.findByText("3 matching assessments");
  expect(summary().getByText("USD", { exact: true })).toBeInTheDocument();
  act(() => {
    window.history.pushState({}, "", viewPath(org, {}, 2, "anomalies", true));
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await screen.findByText("4 matching assessments");
  expect(summary().queryByText("USD", { exact: true })).not.toBeInTheDocument();
});
it("confirms clipboard success only after completion and handles refusal with retry", async () => {
  let finish!: () => void;
  const write = clipboard(
    vi
      .fn()
      .mockRejectedValueOnce(Error("denied"))
      .mockImplementationOnce(
        () =>
          new Promise<void>((r) => {
            finish = r;
          }),
      ),
  );
  open();
  await screen.findByText("4 matching assessments");
  fireEvent.click(copyButton());
  expect(await summary().findByRole("alert")).toHaveTextContent("not copied");
  fireEvent.click(copyButton());
  expect(copyButton()).toBeDisabled();
  expect(
    summary().queryByText(/Summary and view link copied/),
  ).not.toBeInTheDocument();
  await act(async () => finish());
  await summary().findByText(/Summary and view link copied/);
  expect(write).toHaveBeenCalledTimes(2);
});
it("blocks invalid scope before financial reads and shows no prior summary", async () => {
  window.history.replaceState(
    {},
    "",
    viewPath(other, {}, 2, "anomalies", true),
  );
  const gateway = fixture(),
    load = vi.spyOn(gateway, "load"),
    query = vi.spyOn(gateway, "queryExceptions");
  open(gateway);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No financial search was started",
  );
  expect(load).not.toHaveBeenCalled();
  expect(query).not.toHaveBeenCalled();
  expect(
    screen.queryByRole("region", { name: "Applied criteria summary" }),
  ).not.toBeInTheDocument();
});
it("refuses mismatched or oversized links with an explicit summary state", () => {
  const write = clipboard();
  render(
    <AppliedCriteriaSummary
      applied={{ org, filters: { currency: "USD" }, limit: 20 }}
      org={org}
      organization="Synthetic org"
      view="anomalies"
      demo={false}
      coherent
      failed={false}
      makeViewLink={() =>
        "https://fixture.test" +
        viewPath(org, { currency: "EUR" }, 20, "anomalies", false)
      }
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent(
    "cannot be represented safely",
  );
  expect(copyButton()).toBeDisabled();
  expect(write).not.toHaveBeenCalled();
});
it("hides the previous organization's criteria before a different organization succeeds", () => {
  render(
    <AppliedCriteriaSummary
      applied={{
        org,
        filters: { supplier: "Private previous supplier" },
        limit: 20,
      }}
      org={other}
      organization="Other synthetic org"
      view="anomalies"
      demo={false}
      coherent={false}
      failed={false}
      makeViewLink={() => {
        throw Error();
      }}
    />,
  );
  expect(
    screen.queryByText(/Private previous supplier/),
  ).not.toBeInTheDocument();
  expect(copyButton()).toBeDisabled();
});

it("reuses an authorized invoice document label for the independently matching document criterion", async () => {
  const document = "00000000-0000-4000-8000-000000000101";
  window.history.replaceState(
    {},
    "",
    viewPath(
      org,
      { invoice_source_id: source, invoice_document_id: document },
      2,
      "anomalies",
      true,
    ),
  );
  open();
  await screen.findByText("1 matching assessments");
  await waitFor(() =>
    expect(
      summary().getAllByText("AcmeCloud_INV-2026-1042.pdf", { exact: true }),
    ).toHaveLength(2),
  );
  expect(
    summary().queryByText("Selected document label unavailable"),
  ).not.toBeInTheDocument();
});
