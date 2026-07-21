import { NextRequest } from "next/server";
import { BackendSignalListResponse, mapBackendSignalListToFrontend } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, bffSuccess, handleBackendJson } from "@/src/lib/bff-response";
import { isMockMode } from "@/src/lib/mocks/enabled";
import { listMockSignals } from "@/src/lib/mocks/mock-signals";

export async function GET(request: NextRequest) {
  const limit = Number(request.nextUrl.searchParams.get("limit") ?? "50");
  const offset = Number(request.nextUrl.searchParams.get("offset") ?? "0");

  if (isMockMode()) {
    return bffSuccess(listMockSignals(limit, offset));
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/signals?limit=${limit}&offset=${offset}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendSignalListResponse) =>
    mapBackendSignalListToFrontend(payload),
  );
}
