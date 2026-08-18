import { NextRequest } from "next/server";
import {
  BackendImpersonationStartRequest,
  mapBackendImpersonationStart,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ userId: string }> },
) {
  const { userId } = await params;
  const body = (await request.json()) as BackendImpersonationStartRequest;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/impersonation/start/${userId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }

  const bffResponse = await handleBackendJson(backendResponse, mapBackendImpersonationStart);

  // Backend swaps the caller's `access_token` cookie for a scoped impersonation
  // token on success (backend/app/modules/admin/impersonation.py) — forward it,
  // matching the existing Set-Cookie relay pattern in app/api/auth/login/route.ts.
  const setCookieHeader = backendResponse.headers.get("set-cookie");
  if (setCookieHeader) {
    bffResponse.headers.set("set-cookie", setCookieHeader);
  }

  return bffResponse;
}
