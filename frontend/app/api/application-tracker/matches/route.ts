import { NextRequest } from "next/server";
import {
  BackendTrackedMatchListResponse,
  mapBackendTrackedMatchListToFrontend,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const params = new URLSearchParams();
  const status = request.nextUrl.searchParams.get("status");
  const sort = request.nextUrl.searchParams.get("sort");
  const limit = request.nextUrl.searchParams.get("limit");
  const offset = request.nextUrl.searchParams.get("offset");

  if (status) params.set("status", status);
  params.set("sort", sort ?? "newest");
  params.set("limit", limit ?? "20");
  params.set("offset", offset ?? "0");

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/application-tracker/matches?${params.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendTrackedMatchListResponse) =>
    mapBackendTrackedMatchListToFrontend(payload),
  );
}
