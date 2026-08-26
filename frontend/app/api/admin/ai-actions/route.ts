import { NextRequest } from "next/server";
import { mapBackendAiActionList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  if (searchParams.get("candidate_id"))
    query.set("candidate_id", searchParams.get("candidate_id")!);
  if (searchParams.get("recruiter_id"))
    query.set("recruiter_id", searchParams.get("recruiter_id")!);
  if (searchParams.get("action_type")) query.set("action_type", searchParams.get("action_type")!);
  if (searchParams.get("since")) query.set("since", searchParams.get("since")!);
  if (searchParams.get("until")) query.set("until", searchParams.get("until")!);
  if (searchParams.get("cursor")) query.set("cursor", searchParams.get("cursor")!);
  if (searchParams.get("limit")) query.set("limit", searchParams.get("limit")!);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/ai-actions?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAiActionList);
}
