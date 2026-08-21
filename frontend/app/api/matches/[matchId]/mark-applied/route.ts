import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  bffSuccess,
  bffValidationError,
} from "@/src/lib/bff-response";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;
  const body = (await request.json()) as { applied?: boolean };

  if (typeof body.applied !== "boolean") {
    return bffValidationError("applied must be a boolean.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/job-matching/matches/${matchId}/mark-applied`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ applied: body.applied }),
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
