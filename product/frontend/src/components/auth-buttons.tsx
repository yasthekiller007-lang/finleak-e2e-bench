"use client";
import { signIn, signOut } from "next-auth/react";
import { useSyncExternalStore } from "react";

const subscribe = () => () => {};
const readySnapshot = () => true;
const serverSnapshot = () => false;

function useReady() {
  return useSyncExternalStore(subscribe, readySnapshot, serverSnapshot);
}

export function SignInButton() {
  const ready = useReady();
  return (
    <button
      className="button"
      disabled={!ready}
      onClick={() => void signIn("oidc", { callbackUrl: "/documents" })}
    >
      Continue with your identity provider
    </button>
  );
}

export function SignOutButton() {
  const ready = useReady();
  return (
    <button
      className="text-link"
      disabled={!ready}
      onClick={() => void signOut({ callbackUrl: "/login" })}
    >
      Sign out
    </button>
  );
}
