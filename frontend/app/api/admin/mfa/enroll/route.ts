import { mapBackendMfaEnrollResult } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function POST() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/mfa/enroll", { method: "POST" });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendMfaEnrollResult);
}
