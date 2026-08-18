import { mapBackendMfaStatus } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/mfa/status");
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendMfaStatus);
}
