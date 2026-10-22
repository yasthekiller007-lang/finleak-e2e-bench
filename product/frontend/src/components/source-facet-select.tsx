"use client";
import { useEffect, useState } from "react";
import { BusinessFacetSelect } from "@/components/business-facet-select";
import type { FacetOption } from "@/lib/business-facets";
import type { ComponentProps } from "react";
export function SourceFacetSelect({
  id,
  onLabel,
  ...props
}: Omit<ComponentProps<typeof BusinessFacetSelect>, "facet"> & {
  facet: "invoice" | "contract";
  id?: string;
  onLabel?: (id: string, option: FacetOption | null) => void;
}) {
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([props.org, props.facet, id, attempt]);
  const [state, setState] = useState<{
    key: string;
    option?: FacetOption;
    failed?: boolean;
  } | null>(null);
  const { gateway, org, facet, selected } = props;
  useEffect(() => {
    if (!id || selected || !gateway.sourceLabel) return;
    const controller = new AbortController();
    void gateway
      .sourceLabel(org, id, facet, controller.signal)
      .then((option) => {
        if (!controller.signal.aborted)
          setState(
            option.value === id ? { key, option } : { key, failed: true },
          );
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ key, failed: true });
      });
    return () => controller.abort();
  }, [gateway, org, facet, id, selected, key]);
  const resolved = state?.key === key ? state : null;
  const option =
    selected ??
    resolved?.option ??
    (id ? { value: id, label: `Selected ${facet} label unavailable` } : null);
  const known = selected ?? resolved?.option;
  const labelValue = known?.value,
    labelText = known?.label,
    documentId = known?.document_id;
  useEffect(() => {
    onLabel?.(
      id ?? "",
      id && labelValue === id && labelText
        ? { value: id, label: labelText, document_id: documentId }
        : null,
    );
  }, [id, labelValue, labelText, documentId, onLabel]);
  return (
    <div>
      <BusinessFacetSelect {...props} selected={option} />
      {id && !selected && !resolved && gateway.sourceLabel && (
        <small>Loading selected {facet} label…</small>
      )}
      {id && !selected && (!gateway.sourceLabel || resolved?.failed) && (
        <small>
          Selected {facet} label unavailable. Selection kept; no replacement was
          made.{" "}
          {gateway.sourceLabel && (
            <button onClick={() => setAttempt((n) => n + 1)}>
              Retry {facet} label
            </button>
          )}
        </small>
      )}
    </div>
  );
}
