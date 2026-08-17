import { NextRequest } from "next/server";
import { BackendSearchResponse, mapBackendDocumentSearchResponse } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as {
    query?: string;
    limit?: number;
    filters?: Record<string, unknown> | null;
  };

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/documents/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: body.query,
        limit: body.limit ?? 10,
        filters: body.filters ?? null,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendSearchResponse) =>
    mapBackendDocumentSearchResponse(payload),
  );
}
