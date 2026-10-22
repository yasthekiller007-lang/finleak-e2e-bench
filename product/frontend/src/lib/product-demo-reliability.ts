/** Explicit development exercises, isolated from live routes and persistence claims. */
import { createDemoGateway } from "@/lib/product-demo";
import {
  WorkspaceError,
  type Decision,
  type FinancialAuditEntry,
  type WorkspaceGateway,
} from "@/lib/product-workspace";
export type DemoExercise =
  "normal" | "lost-response" | "read-failure" | "conflict" | "stale";
export function createReliabilityDemoGateway(
  exercise: DemoExercise,
): WorkspaceGateway {
  const original = createDemoGateway(),
    rows: FinancialAuditEntry[] = [];
  let failNextRead = false,
    exercised = false;
  async function commit(
    org: string,
    id: string,
    decision: Decision,
    signal: AbortSignal,
  ) {
    const result = (await original.decide(org, id, decision, signal)) as {
      id: string;
    };
    rows.unshift({
      id: `00000000-0000-4000-8000-${String(9900 + rows.length).padStart(12, "0")}`,
      actor_id: "00000000-0000-4000-8000-000000000001",
      action: `finding.${decision.status}`,
      target_id: result.id,
      created_at: new Date().toISOString(),
      detail: {
        table: "financial_finding_decisions",
        reason: decision.reason,
        number: rows.length + 1,
        source: "SYNTHETIC_BROWSER_MEMORY",
      },
    });
    return result;
  }
  return {
    ...original,
    async audit(org, signal) {
      await original.load(org, signal);
      return structuredClone({
        items: rows,
        total: rows.length,
        limit: 100,
        offset: 0,
      });
    },
    async assessment(org, id, signal) {
      if (failNextRead) {
        failNextRead = false;
        throw new WorkspaceError("Synthetic read failure", 503);
      }
      const result = await original.assessment(org, id, signal);
      return exercise === "stale" ? { ...result, stale: true } : result;
    },
    async decide(org, id, decision, signal) {
      if (!exercised && exercise === "conflict") {
        exercised = true;
        await commit(
          org,
          id,
          {
            ...decision,
            status: "needs_review",
            reason: "Synthetic concurrent review by another session",
          },
          signal,
        );
        throw new WorkspaceError(
          "This record changed. Refresh the assessment before making another decision.",
          409,
        );
      }
      const result = await commit(org, id, decision, signal);
      if (!exercised && exercise === "lost-response") {
        exercised = true;
        throw new WorkspaceError(
          "Synthetic response lost after local commit",
          504,
        );
      }
      if (!exercised && exercise === "read-failure") {
        exercised = true;
        failNextRead = true;
      }
      return result;
    },
  };
}
