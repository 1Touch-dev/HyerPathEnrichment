import { NextRequest } from "next/server";
import { adaptCvFeedbackReport } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;
  const body = await request.json().catch(() => ({}));

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_role: body.targetRole ?? null }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  // Backend enqueues feedback generation and returns { job_id, document_id, message }
  // (DocumentUploadResponse — shared with the upload flow, §8.6) — surface the job id
  // so callers can poll job status if they need to, per the same shape used elsewhere.
  return handleBackendJson(backendResponse, (raw: { job_id: string }) => ({ jobId: raw.job_id }), 202);
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}/feedback`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptCvFeedbackReport);
}
