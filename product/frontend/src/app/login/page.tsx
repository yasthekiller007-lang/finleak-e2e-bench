import type { Metadata } from "next";
import type { JSX } from "react";
import { SignInButton } from "@/components/auth-buttons";
import { isAuthConfigured } from "@/lib/auth-config";

export const metadata: Metadata = { title: "Login" };
export const dynamic = "force-dynamic";

type LoginPageProps = { searchParams?: Promise<{ error?: string }> };
// Retain direct no-argument callers while exposing a concrete Next page-props signature.
function LoginPage(): Promise<JSX.Element>;
function LoginPage(props: LoginPageProps): Promise<JSX.Element>;
async function LoginPage({ searchParams }: LoginPageProps = {}) {
  const failed = Boolean((await searchParams)?.error);
  return (
    <main className="login-page">
      <section className="card login-card">
        <span className="brand-mark" aria-hidden="true">
          F
        </span>
        <p className="eyebrow">FINANCIAL LEAKAGE AI</p>
        <h1>Account access</h1>
        <p className="muted">
          Sign in through your organization’s identity provider to access your
          documents.
        </p>
        <p className="login-note">
          Your account’s verified organization membership controls access.
        </p>
        {failed && (
          <p role="alert">
            Sign-in could not be completed. Please try again or contact your
            administrator.
          </p>
        )}
        {isAuthConfigured() ? (
          <SignInButton />
        ) : (
          <p role="status">
            Sign-in is not configured. Contact your administrator.
          </p>
        )}
      </section>
    </main>
  );
}

export default LoginPage;
