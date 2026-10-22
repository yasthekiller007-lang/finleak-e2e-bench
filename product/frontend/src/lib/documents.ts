export type MembershipRole = "owner" | "admin" | "analyst" | "viewer";
export type DocumentType =
  "contract" | "invoice" | "purchase_order" | "credit_note" | "other";
export type Organization = { id: string; name: string; role: MembershipRole };
export type CurrentUser = {
  id: string;
  email: string | null;
  display_name: string;
  organizations: Organization[];
  max_upload_bytes: number;
};
export type FinancialDocument = {
  id: string;
  organization_id: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  sha256: string;
  document_type: DocumentType;
  processing_status:
    | "pending"
    | "queued"
    | "processing"
    | "processed"
    | "failed"
    | "needs_review"
    | "needs_ocr";
  uploaded_at: string;
  uploaded_by: string | null;
};
export type DocumentPage = {
  items: FinancialDocument[];
  total: number;
  limit: number;
  offset: number;
};
export const documentTypes: { value: DocumentType; label: string }[] = [
  { value: "contract", label: "Contract" },
  { value: "invoice", label: "Invoice" },
  { value: "purchase_order", label: "Purchase order" },
  { value: "credit_note", label: "Credit note" },
  { value: "other", label: "Other" },
];

export function validateSelectedFile(
  file: File,
  maxBytes: number,
): string | null {
  if (file.size === 0) return "Choose a nonempty file.";
  if (file.size > maxBytes)
    return `Choose a file smaller than ${Math.floor(maxBytes / 1024 / 1024)} MB.`;
  if (!/\.(pdf|csv|xlsx)$/i.test(file.name))
    return "Choose a PDF, CSV, or XLSX file.";
  return null;
}
