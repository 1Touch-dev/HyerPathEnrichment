import { NextRequest } from "next/server";
import {
  BackendDocumentUploadResponse,
  mapBackendDocumentUploadResponse,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}/reprocess`, {
      method: "POST",
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendDocumentUploadResponse) =>
    mapBackendDocumentUploadResponse(payload),
  );
}
