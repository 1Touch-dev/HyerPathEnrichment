import { NextRequest } from "next/server";
import { mapBackendLinkedInSendBatch } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ batchId: string }> },
) {
  const { batchId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/outreach/linkedin-send-batches/${batchId}/start`, {
      method: "POST",
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendLinkedInSendBatch);
}
