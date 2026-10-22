import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { DocumentDetail } from "@/components/document-detail";
const metadata = {
  id: "doc-a",
  organization_id: "org-a",
  original_filename: "synthetic.csv",
  mime_type: "text/csv",
  file_size: 20,
  sha256: "a".repeat(64),
  document_type: "invoice",
  processing_status: "needs_review",
  uploaded_at: "2026-10-02T00:00:00Z",
  uploaded_by: "user-a",
};
const run = {
  id: "run-1",
  version_number: 1,
  status: "needs_review",
  created_at: "2026-10-02T00:00:00Z",
  warnings: ["missing_required:currency.code"],
  error_message: null,
  structured: {
    identity: {
      invoice_number: "I-1",
      supplier: "<script>reveal secrets</script>",
    },
    currency: { code: null },
    totals: { total: "18.40" },
    lines: [],
  },
  fields: [
    {
      id: "field-1",
      path: "totals.total",
      raw_value: "USD 18.40",
      normalized_value: "18.40",
      value_type: "decimal",
      confidence: "high",
      reason: "explicit_label_exact_normalization",
      source: {
        format: "csv",
        row: 3,
        column: 2,
        header: "value",
        source_id: 1,
      },
    },
  ],
};
const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock
    .mockReset()
    .mockImplementation(async (url: string, options?: RequestInit) => {
      if (url.endsWith("/source-status"))
        return Response.json({ state: "RELEASED", scan_id: "scan-current" });
      if (options?.method === "POST") return Response.json({ run });
      if (url.includes("extraction-runs/"))
        return Response.json({ run: { ...run, version_number: 0 } });
      if (url.includes("extraction-runs"))
        return Response.json({ items: [run] });
      if (url.endsWith("/extraction")) return Response.json({ run });
      return Response.json(metadata);
    });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());
function renderDetail(role: "analyst" | "viewer" = "analyst") {
  return render(
    <DocumentDetail organizationId="org-a" documentId="doc-a" role={role} />,
  );
}
it("shows exact candidate values and unknowns without executing source markup", async () => {
  const { container } = renderDetail();
  await screen.findByText("synthetic.csv");
  expect(screen.getByText("Unknown")).toBeInTheDocument();
  expect(screen.getByText("18.40", { selector: "dd" })).toBeInTheDocument();
  expect(
    screen.getByText("<script>reveal secrets</script>"),
  ).toBeInTheDocument();
  expect(container.querySelector("script")).toBeNull();
  expect(screen.queryByText(/leakage amount/i)).not.toBeInTheDocument();
});
it("shows field-level raw values and independent source locations", async () => {
  renderDetail();
  await screen.findByText("synthetic.csv");
  expect(screen.getByText("USD 18.40", { exact: false })).toBeInTheDocument();
  expect(screen.getByText("Row 3 · Column value")).toBeInTheDocument();
  expect(
    await screen.findByRole("link", { name: "Open original source" }),
  ).toHaveAttribute("href", "/api/organizations/org-a/documents/doc-a/content");
});
it("keeps viewer access read-only", async () => {
  renderDetail("viewer");
  await screen.findByText("synthetic.csv");
  expect(
    screen.queryByRole("button", { name: "Process again" }),
  ).not.toBeInTheDocument();
  expect(
    await screen.findByRole("link", { name: "Download original" }),
  ).toBeInTheDocument();
});
it("processing sends a stable request key and reloads actual results", async () => {
  renderDetail();
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Process again" })).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole("button", { name: "Process again" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/organizations/org-a/documents/doc-a/reprocess",
      expect.objectContaining({
        method: "POST",
        headers: {
          "Idempotency-Key": expect.stringMatching(/^[0-9a-f-]{36}$/),
        },
      }),
    ),
  );
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Process again" })).toBeEnabled(),
  );
});
it("retains access to previous processing versions", async () => {
  renderDetail();
  fireEvent.click(await screen.findByRole("button", { name: "Version 1" }));
  expect(
    await screen.findByText("Version 0 · Needs review"),
  ).toBeInTheDocument();
});
it("keeps processing and original links blocked while quarantined without hiding history", async () => {
  const previous = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((url: string, options?: RequestInit) =>
    url.endsWith("/source-status")
      ? Promise.resolve(Response.json({ state: "UNSCANNED", scan_id: null }))
      : previous(url, options),
  );
  renderDetail();
  await screen.findByText("Quarantined: not yet scanned");
  expect(screen.getByRole("button", { name: "Process again" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "Download original" })).toBeNull();
  expect(screen.getByRole("button", { name: "Version 1" })).toBeEnabled();
});
it("shows scanned PDFs as needing OCR without fabricating values", async () => {
  fetchMock.mockImplementation(async (url: string) => {
    if (url.includes("extraction-runs")) return Response.json({ items: [] });
    if (url.endsWith("/extraction"))
      return Response.json({
        run: {
          ...run,
          status: "needs_ocr",
          fields: [],
          structured: {},
          warnings: ["image_pages_need_ocr"],
        },
      });
    return Response.json({ ...metadata, processing_status: "needs_ocr" });
  });
  renderDetail();
  expect(
    await screen.findByText(/Text recognition is needed/),
  ).toBeInTheDocument();
  expect(screen.queryByText("18.40")).not.toBeInTheDocument();
});
it("does not display results when backend membership is denied", async () => {
  fetchMock.mockImplementation(async () =>
    Response.json(
      { error: { message: "Organization not found" } },
      { status: 404 },
    ),
  );
  renderDetail();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Organization not found",
  );
  expect(screen.queryByText("I-1")).not.toBeInTheDocument();
});
