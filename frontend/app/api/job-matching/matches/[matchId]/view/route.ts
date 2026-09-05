import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, bffSuccess } from "@/src/lib/bff-response";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/job-matching/matches/${matchId}/view`, {
      method: "POST",
    });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }

  // Backend returns 204 No Content — nothing to unwrap/map.
  return bffSuccess(null);
}
