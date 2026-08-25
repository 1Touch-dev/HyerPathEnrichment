import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const role = request.nextUrl.searchParams.get("role") ?? "";
  const limit = request.nextUrl.searchParams.get("limit");

  const query = new URLSearchParams({ role });
  if (limit) query.set("limit", limit);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      `/api/demand-intelligence/top-countries?${query.toString()}`,
    );
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload) => payload);
}
