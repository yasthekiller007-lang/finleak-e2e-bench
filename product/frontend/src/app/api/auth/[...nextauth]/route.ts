import NextAuth from "next-auth";
import type { NextRequest } from "next/server";
import { authOptions, isAuthConfigured } from "@/lib/auth-config";

export const dynamic = "force-dynamic";

async function handle(
  request: NextRequest,
  context: { params: Promise<{ nextauth: string[] }> },
) {
  if (!isAuthConfigured())
    return Response.json(
      { error: "Sign-in is not configured." },
      { status: 503 },
    );
  return NextAuth(authOptions())(request, context);
}

export { handle as GET, handle as POST };
