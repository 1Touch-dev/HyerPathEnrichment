import { NextRequest } from "next/server";
import { BackendMfaVerifyRequest } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, bffSuccess } from "@/src/lib/bff-response";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as BackendMfaVerifyRequest;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/mfa/disable", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }

  // Backend returns 204 No Content — nothing to unwrap/map.
  return bffSuccess(null);
}
