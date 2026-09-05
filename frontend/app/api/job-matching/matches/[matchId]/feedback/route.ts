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
  const body = (await request.json()) as { feedback?: "up" | "down" };

  if (body.feedback !== "up" && body.feedback !== "down") {
    return bffValidationError('feedback must be "up" or "down".');
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/job-matching/matches/${matchId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedback: body.feedback }),
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
