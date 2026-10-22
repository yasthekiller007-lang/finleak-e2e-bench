import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentWorkspace } from "@/components/document-workspace";
import { validateSelectedFile } from "@/lib/documents";
import type { CurrentUser } from "@/lib/documents";

const user: CurrentUser = {
  id: "user-a",
  email: null,
  display_name: "User A",
  max_upload_bytes: 20971520,
  organizations: [
    { id: "org-a", name: "Organization A", role: "analyst" },
    { id: "org-b", name: "Organization B", role: "viewer" },
  ],
};
const document = {
  id: "doc-a",
  organization_id: "org-a",
  original_filename: "invoice.csv",
  mime_type: "text/csv",
  file_size: 20,
  sha256: "0".repeat(64),
  document_type: "invoice",
  processing_status: "pending",
  uploaded_by: "user-a",
  uploaded_at: "2026-10-02T00:00:00Z",
};
const fetchMock = vi.fn();
class UploadRequest {
  static latest: UploadRequest;
  upload = {
    onprogress: null as
      | ((event: {
          loaded: number;
          total: number;
          lengthComputable: boolean;
        }) => void)
      | null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  timeout = 0;
  status = 201;
  responseText = JSON.stringify(document);
  open = vi.fn();
  send = vi.fn();
  abort = vi.fn();
  constructor() {
    UploadRequest.latest = this;
  }
}
beforeEach(() => {
  fetchMock
    .mockReset()
    .mockResolvedValue(
      Response.json({ items: [document], total: 1, limit: 20, offset: 0 }),
    );
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("XMLHttpRequest", UploadRequest);
});
afterEach(() => vi.unstubAllGlobals());

describe("authenticated documents workspace", () => {
  it("loads real metadata and attachment links from selected organization", async () => {
    render(<DocumentWorkspace user={user} />);
    expect(
      await screen.findByRole("cell", { name: "invoice.csv" }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/organizations/org-a/documents?limit=20&offset=0",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(screen.getByRole("link", { name: /Download/ })).toHaveAttribute(
      "href",
      "/api/organizations/org-a/documents/doc-a/content",
    );
    expect(screen.getByText("Ready to process")).toBeInTheDocument();
  });
  it("changes organizations and makes viewer access read-only", async () => {
    render(<DocumentWorkspace user={user} />);
    await screen.findByRole("cell", { name: "invoice.csv" });
    fireEvent.change(screen.getByLabelText("Organization"), {
      target: { value: "org-b" },
    });
    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith(
        "/api/organizations/org-b/documents?limit=20&offset=0",
        expect.anything(),
      ),
    );
    expect(screen.queryByLabelText("File")).not.toBeInTheDocument();
    expect(screen.getByText(/viewer role/)).toBeInTheDocument();
  });
  it("cannot upload before administrator assigns organization membership", () => {
    render(<DocumentWorkspace user={{ ...user, organizations: [] }} />);
    expect(screen.getByText("No organization access yet")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("File")).not.toBeInTheDocument();
  });
  it("validates size and extension without claiming client checks establish security", () => {
    expect(validateSelectedFile(new File([], "invoice.csv"), 100)).toMatch(
      /empty/i,
    );
    expect(
      validateSelectedFile(new File(["x".repeat(101)], "invoice.csv"), 100),
    ).toMatch(/smaller/i);
    expect(validateSelectedFile(new File(["x"], "script.exe"), 100)).toMatch(
      /PDF/,
    );
    expect(
      validateSelectedFile(new File(["x"], "invoice.csv"), 100),
    ).toBeNull();
  });
  it("submits classification, shows progress, reloads after success and clears selection", async () => {
    render(<DocumentWorkspace user={user} />);
    await screen.findByRole("cell", { name: "invoice.csv" });
    fireEvent.change(screen.getByLabelText("File"), {
      target: {
        files: [
          new File(["ref,amount\n1,20"], "invoice.csv", { type: "text/csv" }),
        ],
      },
    });
    fireEvent.change(screen.getByLabelText("Document type"), {
      target: { value: "credit_note" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Upload document/i }));
    const request = UploadRequest.latest;
    expect(request.open).toHaveBeenCalledWith(
      "POST",
      "/api/organizations/org-a/documents",
    );
    expect(
      (request.send.mock.calls[0][0] as FormData).get("document_type"),
    ).toBe("credit_note");
    const { act } = await import("@testing-library/react");
    act(() =>
      request.upload.onprogress?.({
        loaded: 50,
        total: 100,
        lengthComputable: true,
      }),
    );
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "50");
    act(() => request.onload?.());
    expect(await screen.findByText(/Document uploaded/)).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("File")).toHaveValue("");
  });
  it("reports backend errors without creating a successful upload state", async () => {
    render(<DocumentWorkspace user={user} />);
    await screen.findByRole("cell", { name: "invoice.csv" });
    fireEvent.change(screen.getByLabelText("File"), {
      target: { files: [new File(["x"], "invoice.csv")] },
    });
    fireEvent.click(screen.getByRole("button", { name: /Upload document/i }));
    const request = UploadRequest.latest;
    request.status = 409;
    request.responseText = JSON.stringify({
      error: { message: "Duplicate document" },
    });
    const { act } = await import("@testing-library/react");
    act(() => request.onload?.());
    expect(screen.getByRole("alert")).toHaveTextContent("Duplicate document");
    expect(screen.queryByText(/Document uploaded/)).not.toBeInTheDocument();
  });
});
