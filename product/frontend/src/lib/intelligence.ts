import type { FinancialDocument } from "@/lib/documents";

export type ExtractionField = {
  id: string;
  path: string;
  raw_value: string;
  normalized_value: string | boolean | null;
  value_type: string;
  confidence: "high" | "medium" | "low";
  reason: string;
  source: Record<string, string | number>;
};
export type ExtractionRun = {
  id: string;
  document_id: string;
  organization_id: string;
  version_number: number;
  previous_run_id: string | null;
  status: FinancialDocument["processing_status"];
  created_at: string;
  finished_at: string | null;
  error_message: string | null;
  warnings: string[];
  structured: Record<
    string,
    | Record<string, string | boolean | null>
    | Record<string, string | boolean | null>[]
  >;
  fields: ExtractionField[];
};
export const statusLabels: Record<
  FinancialDocument["processing_status"],
  string
> = {
  pending: "Ready to process",
  queued: "Waiting",
  processing: "Processing",
  processed: "Extracted",
  needs_review: "Needs review",
  needs_ocr: "Needs OCR",
  failed: "Failed",
};
export function fieldLabel(path: string) {
  return path.replaceAll(".", " · ").replaceAll("_", " ");
}
export function warningLabel(warning: string) {
  const [code, field] = warning.split(":");
  const labels: Record<string, string> = {
    image_content_not_interpreted:
      "Images may contain additional information. Review the original document.",
    image_pages_need_ocr:
      "Some image pages need text recognition before they can be reviewed.",
    secondary_document_extraction_deferred:
      "Structured extraction for this document type is not available yet.",
    unrecognized_content_requires_review:
      "Some content could not be mapped to supported fields. Review the original document.",
    spreadsheet_formulas_ignored:
      "Spreadsheet formulas were ignored. Upload explicit values if needed.",
    line_items_missing: "No supported line-item structure was found.",
    missing_required: "Missing information",
    ambiguous_value: "Ambiguous value",
    conflicting_values: "Conflicting source values",
    incomplete_lines: "Incomplete invoice line",
    incomplete_pricing: "Incomplete pricing entry",
  };
  return `${labels[code] ?? "Review needed"}${field ? `: ${fieldLabel(field)}` : ""}`;
}
