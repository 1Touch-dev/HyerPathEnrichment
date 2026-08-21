import { NextRequest } from "next/server";
import { mapBackendAdminDocumentList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  if (searchParams.get("cursor")) query.set("cursor", searchParams.get("cursor")!);
  if (searchParams.get("limit")) query.set("limit", searchParams.get("limit")!);
  if (searchParams.get("processing_status")) {
    query.set("processing_status", searchParams.get("processing_status")!);
  }
  if (searchParams.get("deleted")) query.set("deleted", searchParams.get("deleted")!);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/documents?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminDocumentList);
}
