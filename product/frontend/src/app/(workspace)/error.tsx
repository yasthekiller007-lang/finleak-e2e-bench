"use client";

export default function WorkspaceError({ reset }: { reset: () => void }) {
  return (
    <section className="card settings-card">
      <h1>Workspace temporarily unavailable</h1>
      <p className="muted">Please retry or contact your administrator.</p>
      <button className="button" onClick={reset}>
        Retry
      </button>
    </section>
  );
}
