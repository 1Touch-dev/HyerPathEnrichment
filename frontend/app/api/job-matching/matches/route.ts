import { NextRequest } from "next/server";
import {
  BackendJobMatchListResponse,
  mapBackendJobMatchListToFrontend,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const limit = Number(request.nextUrl.searchParams.get("limit") ?? "20");
  const offset = Number(request.nextUrl.searchParams.get("offset") ?? "0");

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      `/api/job-matching/matches?limit=${limit}&offset=${offset}`,
    );
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendJobMatchListResponse) =>
    mapBackendJobMatchListToFrontend(payload),
  );
}
