import { NextRequest } from "next/server";
import { BackendDocumentMetadata, mapBackendDocumentList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const limit = Number(request.nextUrl.searchParams.get("limit") ?? "50");

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents?limit=${limit}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendDocumentMetadata[]) =>
    mapBackendDocumentList(payload),
  );
}
