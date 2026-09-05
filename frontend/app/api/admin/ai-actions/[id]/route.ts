import { NextRequest } from "next/server";
import { mapBackendAiAction } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/ai-actions/${id}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAiAction);
}
