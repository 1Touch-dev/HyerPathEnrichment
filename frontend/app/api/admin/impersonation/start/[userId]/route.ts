import { NextRequest } from "next/server";
import {
  BackendImpersonationStartRequest,
  mapBackendImpersonationStart,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { forwardBackendSetCookies } from "@/src/lib/forward-backend-cookies";

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
  forwardBackendSetCookies(backendResponse, bffResponse);
  return bffResponse;
}
