import { NextRequest } from "next/server";
import { mapBackendAdminJobPostingList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  if (searchParams.get("cursor")) query.set("cursor", searchParams.get("cursor")!);
  if (searchParams.get("limit")) query.set("limit", searchParams.get("limit")!);
  if (searchParams.get("moderation_status")) {
    query.set("moderation_status", searchParams.get("moderation_status")!);
  }
  if (searchParams.get("source")) query.set("source", searchParams.get("source")!);
  if (searchParams.get("is_active")) query.set("is_active", searchParams.get("is_active")!);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/job-postings?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminJobPostingList);
}
