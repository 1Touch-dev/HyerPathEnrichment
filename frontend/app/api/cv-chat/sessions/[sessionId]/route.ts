import { NextRequest } from "next/server";
import { adaptCvChatSession } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/cv-chat/sessions/${sessionId}`, {
      method: "GET",
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptCvChatSession);
}
