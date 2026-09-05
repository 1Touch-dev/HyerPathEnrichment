import { NextRequest } from "next/server";
import { mapBackendLinkedInSendTask } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

type SkipLinkedInTaskRequestBody = {
  outcomeNote?: string | null;
};

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await params;
  const body = (await request.json().catch(() => ({}))) as SkipLinkedInTaskRequestBody;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/outreach/linkedin-tasks/${taskId}/skip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome_note: body.outcomeNote ?? null }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendLinkedInSendTask);
}
