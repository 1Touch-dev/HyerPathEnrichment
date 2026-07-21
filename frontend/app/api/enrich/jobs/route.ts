import { NextRequest } from "next/server";
import { BackendJobListResponse, mapBackendJobListToFrontend } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, bffSuccess, handleBackendJson } from "@/src/lib/bff-response";
import { isMockMode } from "@/src/lib/mocks/enabled";
import { listMockJobs } from "@/src/lib/mocks/mock-jobs";

export async function GET(request: NextRequest) {
  const limit = Number(request.nextUrl.searchParams.get("limit") ?? "50");
  const offset = Number(request.nextUrl.searchParams.get("offset") ?? "0");

  if (isMockMode()) {
    const { jobs, total } = listMockJobs(limit, offset);
    return bffSuccess({ jobs, total, limit, offset });
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/enrich?limit=${limit}&offset=${offset}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendJobListResponse) =>
    mapBackendJobListToFrontend(payload),
  );
}
