import { NextRequest } from "next/server";
import { mapBackendMfaEnrollResult } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { ensureIdempotencyHeaders } from "@/src/lib/idempotency";

export async function POST(request: NextRequest) {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/mfa/enroll", {
      method: "POST",
      headers: ensureIdempotencyHeaders(request, "admin-mfa-enroll"),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendMfaEnrollResult);
}
