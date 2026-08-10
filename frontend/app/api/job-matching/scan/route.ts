import { BackendScanTriggerResponse } from "@/src/lib/generated/api-schemas";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function POST() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/job-matching/scan", { method: "POST" });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendScanTriggerResponse) => ({
    message: payload.message,
    scanEnqueued: payload.scan_enqueued,
  }));
}
