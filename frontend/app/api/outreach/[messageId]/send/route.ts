import { NextRequest } from "next/server";
import { adaptOutreachMessage } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ messageId: string }> },
) {
  const { messageId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/outreach/${messageId}/send`, { method: "POST" });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(backendResponse, adaptOutreachMessage);
}
