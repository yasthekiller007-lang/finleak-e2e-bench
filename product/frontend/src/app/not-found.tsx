import Link from "next/link";

export default function NotFound() {
  return (
    <main className="login-page">
      <section className="card login-card">
        <p className="eyebrow">404</p>
        <h1>Page not found</h1>
        <p className="muted">The page you requested is not available.</p>
        <Link className="button" href="/dashboard">
          Return to overview
        </Link>
      </section>
    </main>
  );
}
