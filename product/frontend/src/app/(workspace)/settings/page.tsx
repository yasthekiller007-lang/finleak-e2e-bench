import type { Metadata } from "next";
import { PageHeading } from "@/components/page-heading";
import { getCurrentUser } from "@/lib/backend";
export const metadata: Metadata = { title: "Settings" };
export const dynamic = "force-dynamic";
export default async function SettingsPage() {
  const user = await getCurrentUser();
  return (
    <>
      <PageHeading
        eyebrow="ACCOUNT AND ACCESS"
        title="Settings"
        description="Verified account and current organization roles."
      />
      <section className="card settings-card">
        <h2>Account access</h2>
        <p>{user?.display_name ?? "Account unavailable"}</p>
        <p>
          Organization membership is controlled by an authorized operator. There
          is no public signup or self-service role grant.
        </p>
        <ul>
          {user?.organizations.map((org) => (
            <li key={org.id}>
              {org.name}: current role {org.role}
            </li>
          ))}
        </ul>
        {!user?.organizations.length && <p>No current organization access.</p>}
        <p>
          Signing out ends this application session. Your identity provider may
          retain SSO; already-issued API tokens are not instantly revoked by
          application logout. Current membership revocation and offboarding
          remain authoritative.
        </p>
        <p>
          Use the pilot guide before uploading evidence. Operator enrollment and
          a separate pilot GO decision are required before customer use.
        </p>
      </section>
    </>
  );
}
