import { NextRequest } from "next/server";
import { mapBackendAuditLogList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  if (searchParams.get("cursor")) query.set("cursor", searchParams.get("cursor")!);
  if (searchParams.get("limit")) query.set("limit", searchParams.get("limit")!);
  if (searchParams.get("action")) query.set("action", searchParams.get("action")!);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/audit-logs?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAuditLogList);
}
