import { NextRequest } from "next/server";
import { mapBackendLinkedInSendTask } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/outreach/linkedin-tasks/${taskId}/claim`, {
      method: "POST",
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendLinkedInSendTask);
}
