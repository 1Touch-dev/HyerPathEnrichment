import { NextRequest } from "next/server";
import { adaptCvCompleteness } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}/completeness`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptCvCompleteness);
}
