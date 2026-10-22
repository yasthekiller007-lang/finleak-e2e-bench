"use client";
import { useState } from "react";
import {
  withSyntheticSavedViews,
  type SavedViewExercise,
  type RenameExercise,
} from "@/lib/product-demo-saved-views";
import { ExceptionViewWorkspace } from "@/components/exception-view-workspace";
import { ProductConsole } from "@/components/product-console";
import { demoUser } from "@/lib/product-demo";
import {
  createReliabilityDemoGateway,
  type DemoExercise,
} from "@/lib/product-demo-reliability";
import type { ProductView } from "@/lib/product-workspace";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import { withSyntheticBusinessFacets } from "@/lib/product-demo-business-facets";
import { withSyntheticServerQuery } from "@/lib/product-demo-server-query";

function DemoSession({
  view,
  initialInvoice = "",
  initialAssessment = "",
  exercise,
  savedExercise,
  initialSearch = "",
}: {
  view: ProductView;
  initialInvoice?: string;
  initialAssessment?: string;
  exercise: DemoExercise;
  savedExercise: SavedViewExercise | RenameExercise;
  initialSearch?: string;
}) {
  const [gateway] = useState(() =>
    withSyntheticSavedViews(
      withSyntheticBusinessFacets(
        withSyntheticServerQuery(
          withSyntheticExceptionContext(createReliabilityDemoGateway(exercise)),
        ),
      ),
      true,
      savedExercise,
    ),
  );
  if (view === "anomalies" || view === "review")
    return (
      <ExceptionViewWorkspace
        user={demoUser}
        view={view}
        demo
        gateway={gateway}
        initialSearch={initialSearch}
      />
    );
  return (
    <ProductConsole
      key={`${view}:${initialInvoice}:${initialAssessment}`}
      user={demoUser}
      gateway={gateway}
      view={view}
      initialInvoice={initialInvoice}
      initialAssessment={initialAssessment}
      demo
    />
  );
}

export function ProductDemoWorkspace(props: {
  view: ProductView;
  initialSearch?: string;
  initialInvoice?: string;
  initialAssessment?: string;
}) {
  const [exercise, setExercise] = useState<DemoExercise>("normal");
  const [savedExercise, setSavedExercise] = useState<
    SavedViewExercise | RenameExercise
  >("normal");
  return (
    <>
      <div className="p-demo-controls">
        <label>
          Synthetic development exercise
          <select
            aria-label="Synthetic development exercise"
            value={exercise}
            onChange={(e) => setExercise(e.target.value as DemoExercise)}
          >
            <option value="normal">Normal decision & local audit</option>
            <option value="lost-response">
              Response lost after local save
            </option>
            <option value="read-failure">
              Read unavailable after acknowledgment
            </option>
            <option value="conflict">Concurrent review conflict (409)</option>
            <option value="stale">Changed source inputs</option>
          </select>
        </label>
        <label>
          Synthetic saved view exercise
          <select
            aria-label="Synthetic saved view exercise"
            value={savedExercise}
            onChange={(e) =>
              setSavedExercise(
                e.target.value as SavedViewExercise | RenameExercise,
              )
            }
          >
            <option value="normal">Normal saved-view response</option>
            <option value="lost-applied">
              Lost response · proposal recorded in memory
            </option>
            <option value="lost-previous">
              Lost response · previous criteria remain
            </option>
            <option value="lost-different">
              Lost response · later divergent state
            </option>
            <option value="lost-read-once">
              Lost response · next read unavailable
            </option>
            <option value="rename-lost-applied">
              Rename response lost · proposed name recorded
            </option>
            <option value="rename-lost-previous">
              Rename response lost · previous name remains
            </option>
            <option value="rename-lost-different">
              Rename response lost · concurrent criteria change
            </option>
            <option value="rename-lost-read-once">
              Rename response lost · next read unavailable
            </option>
          </select>
        </label>
        <span>No PostgreSQL, identity provider or live API is used here.</span>
      </div>
      <DemoSession
        key={`${props.view}:${props.initialInvoice}:${props.initialAssessment}:${exercise}:${savedExercise}`}
        {...props}
        exercise={exercise}
        savedExercise={savedExercise}
      />
    </>
  );
}
