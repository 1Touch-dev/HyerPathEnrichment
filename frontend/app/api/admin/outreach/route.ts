import { NextRequest } from "next/server";
import { mapBackendAdminOutreachMessageList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  if (searchParams.get("cursor")) query.set("cursor", searchParams.get("cursor")!);
  if (searchParams.get("limit")) query.set("limit", searchParams.get("limit")!);
  if (searchParams.get("status")) query.set("status", searchParams.get("status")!);
  if (searchParams.get("admin_blocked")) {
    query.set("admin_blocked", searchParams.get("admin_blocked")!);
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/outreach?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminOutreachMessageList);
}
