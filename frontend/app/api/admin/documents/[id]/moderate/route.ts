import { NextRequest } from "next/server";
import { mapBackendAdminDocument } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import type { BackendModerateDocumentRequest } from "@/src/lib/types";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const body = (await request.json()) as BackendModerateDocumentRequest;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/documents/${id}/moderate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminDocument);
}
