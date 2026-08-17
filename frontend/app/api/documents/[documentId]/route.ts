import { NextRequest } from "next/server";
import { BackendDocumentDetailResponse, mapBackendDocumentDetail } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  bffSuccess,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendDocumentDetailResponse) =>
    mapBackendDocumentDetail(payload),
  );
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}`, {
      method: "DELETE",
    });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }

  // Backend returns 204 No Content — nothing to unwrap/map.
  return bffSuccess(null);
}
