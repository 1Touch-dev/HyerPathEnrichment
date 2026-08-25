import { NextRequest } from "next/server";
import { mapBackendLinkedInTaskList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const statusFilter = request.nextUrl.searchParams.get("status");
  const query = new URLSearchParams();
  if (statusFilter) query.set("status", statusFilter);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/outreach/linkedin-tasks?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendLinkedInTaskList);
}
