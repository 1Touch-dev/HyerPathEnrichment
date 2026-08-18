import { NextRequest } from "next/server";
import { mapBackendJobMatchAnalytics } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  if (searchParams.get("refresh")) query.set("refresh", searchParams.get("refresh")!);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/analytics/job-matches?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendJobMatchAnalytics);
}
