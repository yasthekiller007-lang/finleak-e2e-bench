import type { Assessment } from "@/lib/financial";
export type ExceptionQuery = {
  q?: string;
  invoice_source_id?: string;
  invoice_document_id?: string;
  outcome?: string;
  decision_status?: string;
  currency?: string;
  supplier?: string;
  contract_source_id?: string;
  missing_contract?: boolean;
  created_from?: string;
  created_to?: string;
  current?: boolean;
  needs_review?: boolean;
  sort?: string;
};
export type ExceptionRow = Assessment & {
  invoice_filename?: string | null;
  invoice_document_id?: string | null;
  contract_filename?: string | null;
};
export type ExceptionPage = {
  items: ExceptionRow[];
  total: number;
  total_exact: boolean;
  limit: number;
  offset: number;
  has_more: boolean;
  next_cursor: string | null;
  pagination: string;
  consistency: string;
  coverage: string;
};
export function exceptionsPath(
  filters: ExceptionQuery,
  limit: number,
  after: string | null,
) {
  const params = new URLSearchParams({
    pagination: "cursor",
    limit: String(limit),
  });
  for (const [key, value] of Object.entries(filters))
    if (value !== undefined && value !== "" && value !== false)
      params.set(key, String(value));
  if (after) params.set("after", after);
  return `financial/evaluations?${params}`;
}
