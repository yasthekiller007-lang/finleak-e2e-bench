/** Explicit synthetic context layered over V1.1; never imported by live gateways. */
import type { Assessment } from "@/lib/financial";
import type { WorkspaceData, WorkspaceGateway } from "@/lib/product-workspace";
export function withSyntheticExceptionContext(
  gateway: WorkspaceGateway,
): WorkspaceGateway {
  let data: WorkspaceData | undefined;
  const enrich = (assessment: Assessment): Assessment => {
    const source = data?.sources.items.find(
      (s) => s.id === assessment.invoice_source_id,
    );
    const filename =
      data?.documents.items.find((d) => d.id === source?.document_id)
        ?.original_filename ?? "";
    const contractDoc = assessment.snapshot?.inputs.find(
      (r) => r.kind === "term",
    )?.provenance[0]?.document_id;
    const contract = data?.sources.items.find(
      (s) => s.kind === "contract" && s.document_id === contractDoc,
    );
    return {
      ...assessment,
      queue_context: {
        supplier_party: filename.startsWith("AcmeCloud")
          ? "AcmeCloud"
          : filename.startsWith("Veridian")
            ? "Veridian"
            : filename.startsWith("Atlas")
              ? "Atlas"
              : null,
        contract_source_id: contract?.id ?? null,
        contract_references: contract ? ["DEMO contractual reference"] : [],
      },
    };
  };
  return {
    ...gateway,
    async load(...args) {
      data = await gateway.load(...args);
      return {
        ...data,
        assessments: {
          ...data.assessments,
          items: data.assessments.items.map(enrich),
        },
      };
    },
    async assessment(...args) {
      return enrich(await gateway.assessment(...args));
    },
    async assessments(...args) {
      const page = await gateway.assessments(...args);
      return { ...page, items: page.items.map(enrich) };
    },
  };
}
