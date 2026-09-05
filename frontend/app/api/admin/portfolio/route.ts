import { NextRequest } from "next/server";
import { mapBackendAdminPortfolioProfileList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  if (searchParams.get("cursor")) query.set("cursor", searchParams.get("cursor")!);
  if (searchParams.get("limit")) query.set("limit", searchParams.get("limit")!);
  if (searchParams.get("is_published"))
    query.set("is_published", searchParams.get("is_published")!);
  if (searchParams.get("admin_hidden"))
    query.set("admin_hidden", searchParams.get("admin_hidden")!);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/portfolio?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminPortfolioProfileList);
}
