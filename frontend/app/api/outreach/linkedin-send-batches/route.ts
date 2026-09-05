import { NextRequest } from "next/server";
import { mapBackendLinkedInSendBatch } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

type CreateLinkedInSendBatchRequestBody = {
  multiloginProfileId?: string;
  maxSendsPerDay?: number;
  taskIds?: string[];
};

/**
 * `maxSendsPerDay` is required by the backend schema (422 without it) — mirrored
 * here as a BFF-level validation so the operator gets an immediate, clear error
 * rather than an opaque backend 422 passthrough for the most common mistake.
 */
export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as CreateLinkedInSendBatchRequestBody;

  if (typeof body?.multiloginProfileId !== "string" || !body.multiloginProfileId.trim()) {
    return bffValidationError("multiloginProfileId is required.");
  }
  if (typeof body?.maxSendsPerDay !== "number" || body.maxSendsPerDay <= 0) {
    return bffValidationError("maxSendsPerDay is required and must be a positive integer.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/outreach/linkedin-send-batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        multilogin_profile_id: body.multiloginProfileId,
        max_sends_per_day: body.maxSendsPerDay,
        task_ids: body.taskIds ?? [],
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendLinkedInSendBatch);
}
