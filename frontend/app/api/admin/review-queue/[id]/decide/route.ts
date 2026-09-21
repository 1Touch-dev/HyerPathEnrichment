import { NextRequest } from "next/server";
import { mapBackendAdminReviewQueueItem } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { forwardIdempotencyHeader } from "@/src/lib/idempotency";
import type { BackendAdminReviewQueueDecideRequest } from "@/src/lib/types";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = (await request.json()) as BackendAdminReviewQueueDecideRequest;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/review-queue/${id}/decide`, {
      method: "POST",
      headers: forwardIdempotencyHeader(request, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminReviewQueueItem);
}
