"use client";

import Link from "next/link";
import { statusLabels } from "@/lib/intelligence";
import { useEffect, useRef, useState } from "react";
import { documentTypes, validateSelectedFile } from "@/lib/documents";
import type {
  CurrentUser,
  DocumentPage,
  DocumentType,
  FinancialDocument,
} from "@/lib/documents";

const emptyPage: DocumentPage = { items: [], total: 0, limit: 20, offset: 0 };

function errorMessage(body: unknown, fallback: string): string {
  if (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof body.error === "object" &&
    body.error !== null &&
    "message" in body.error &&
    typeof body.error.message === "string"
  )
    return body.error.message;
  return fallback;
}

export function DocumentWorkspace({ user }: { user: CurrentUser }) {
  const [organizationId, setOrganizationId] = useState(
    user.organizations[0]?.id ?? "",
  );
  const [page, setPage] = useState(emptyPage);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const requestKey = `${organizationId}:${offset}:${revision}`;
  const [completedRequestKey, setCompletedRequestKey] = useState("");
  const loading = completedRequestKey !== requestKey;
  const uploadRequest = useRef<XMLHttpRequest | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [type, setType] = useState<DocumentType>("contract");
  const [progress, setProgress] = useState<number | null>(null);
  const organization = user.organizations.find(
    (org) => org.id === organizationId,
  );

  useEffect(() => {
    if (!organizationId) return;
    const controller = new AbortController();
    fetch(
      `/api/organizations/${organizationId}/documents?limit=20&offset=${offset}`,
      { cache: "no-store", signal: controller.signal },
    )
      .then(async (response) => {
        const body: unknown = await response.json();
        if (!response.ok)
          throw new Error(errorMessage(body, "Unable to load documents."));
        return body as DocumentPage;
      })
      .then((result) => {
        if (!controller.signal.aborted) {
          setPage(result);
          setError("");
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(
            cause instanceof Error
              ? cause.message
              : "Unable to load documents.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setCompletedRequestKey(requestKey);
      });
    return () => controller.abort();
  }, [organizationId, offset, revision, requestKey]);

  useEffect(() => () => uploadRequest.current?.abort(), []);

  if (!organization)
    return (
      <section className="card settings-card">
        <h2>No organization access yet</h2>
        <p className="muted">
          Ask your administrator to add your verified account to an
          organization.
        </p>
      </section>
    );

  function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!file) {
      setError("Choose a file first.");
      return;
    }
    const validation = validateSelectedFile(file, user.max_upload_bytes);
    if (validation) {
      setError(validation);
      return;
    }
    const data = new FormData();
    data.append("file", file);
    data.append("document_type", type);
    const request = new XMLHttpRequest();
    uploadRequest.current = request;
    request.open("POST", `/api/organizations/${organizationId}/documents`);
    request.timeout = 60000;
    request.upload.onprogress = (update) => {
      if (update.lengthComputable)
        setProgress(Math.round((update.loaded / update.total) * 100));
    };
    request.onerror = () => {
      setProgress(null);
      setError("Upload failed. Check your connection and retry.");
    };
    request.ontimeout = () => {
      setProgress(null);
      setError("Upload timed out. Check the document list before retrying.");
      setRevision((value) => value + 1);
    };
    request.onload = () => {
      setProgress(null);
      let body: unknown;
      try {
        body = JSON.parse(request.responseText);
      } catch {
        setError("Upload failed.");
        return;
      }
      if (request.status !== 201) {
        setError(errorMessage(body, "Upload failed."));
        return;
      }
      setNotice(
        "Document uploaded. It is quarantined until an explicit clean scan and owner/admin release. No analysis has run.",
      );
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      setOffset(0);
      setRevision((value) => value + 1);
    };
    setProgress(0);
    request.send(data);
  }

  return (
    <>
      <section className="card settings-card organization-picker">
        <label htmlFor="organization">Organization</label>
        <select
          id="organization"
          value={organizationId}
          disabled={progress !== null}
          onChange={(event) => {
            setOrganizationId(event.target.value);
            setPage(emptyPage);
            setOffset(0);
            setNotice("");
            setError("");
            setFile(null);
          }}
        >
          {user.organizations.map((org) => (
            <option key={org.id} value={org.id}>
              {org.name}
            </option>
          ))}
        </select>
        <span className="badge">{organization.role}</span>
      </section>
      {error && (
        <div role="alert" className="error-notice">
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="notice">
          {notice}
        </div>
      )}
      {organization.role !== "viewer" ? (
        <section className="card settings-card upload-card">
          <h2>Upload a document</h2>
          <p className="muted">
            PDF, UTF-8 CSV, or XLSX · Maximum{" "}
            {Math.floor(user.max_upload_bytes / 1024 / 1024)} MB
          </p>
          <form onSubmit={upload}>
            <label htmlFor="document-file">File</label>
            <input
              ref={fileInput}
              id="document-file"
              name="file"
              type="file"
              accept=".pdf,.csv,.xlsx"
              disabled={progress !== null}
              onChange={(event) => {
                const selected = event.target.files?.[0] ?? null;
                setFile(selected);
                setError(
                  selected
                    ? (validateSelectedFile(selected, user.max_upload_bytes) ??
                        "")
                    : "",
                );
              }}
            />
            <label htmlFor="document-type">Document type</label>
            <select
              id="document-type"
              value={type}
              disabled={progress !== null}
              onChange={(event) => setType(event.target.value as DocumentType)}
            >
              {documentTypes.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <button
              className="button"
              type="submit"
              disabled={progress !== null || !file}
            >
              Upload document
            </button>
            {progress !== null && (
              <div role="status">
                <progress
                  aria-label="Upload progress"
                  value={progress}
                  max={100}
                />{" "}
                {progress < 100 ? `${progress}% uploaded` : "Saving document…"}
              </div>
            )}
          </form>
        </section>
      ) : (
        <p className="notice">
          Your viewer role allows reading documents and downloading released
          originals.
        </p>
      )}
      <section className="card">
        <div className="section-heading">
          <h2>Document library</h2>
          <span className="badge">{page.total} documents</span>
        </div>
        {error ? (
          <p>
            Document list unavailable. Refresh before using previous results.
          </p>
        ) : loading ? (
          <p role="status" className="empty-state">
            Loading documents…
          </p>
        ) : page.items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Uploaded</th>
                  <th>Content</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((document: FinancialDocument) => (
                  <tr key={document.id}>
                    <td>
                      <Link
                        className="text-link"
                        href={`/documents/${organizationId}/${document.id}`}
                      >
                        {document.original_filename}
                      </Link>
                    </td>
                    <td>
                      {
                        documentTypes.find(
                          (item) => item.value === document.document_type,
                        )?.label
                      }
                    </td>
                    <td>
                      <span className="badge">
                        {statusLabels[document.processing_status]}
                      </span>
                    </td>
                    <td>
                      <time dateTime={document.uploaded_at}>
                        {new Date(document.uploaded_at).toLocaleDateString()}
                      </time>
                    </td>
                    <td>
                      <a
                        className="text-link"
                        href={`/api/organizations/${organizationId}/documents/${document.id}/content`}
                      >
                        Download
                        <span className="sr-only">
                          {" "}
                          {document.original_filename}
                        </span>
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          !error && (
            <div className="empty-state">
              <h2>No documents uploaded</h2>
              <p className="muted">
                Documents uploaded to this organization will appear here.
              </p>
            </div>
          )
        )}
        <div className="pagination">
          <button
            disabled={loading || offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            Previous
          </button>
          <span>Page {Math.floor(offset / 20) + 1}</span>
          <button
            disabled={loading || offset + page.limit >= page.total}
            onClick={() => setOffset(offset + 20)}
          >
            Next
          </button>
        </div>
      </section>
    </>
  );
}
