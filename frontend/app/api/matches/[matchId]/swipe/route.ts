import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  bffSuccess,
  bffValidationError,
} from "@/src/lib/bff-response";

const VALID_DIRECTIONS = new Set(["left", "right", "up"]);

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;
  const body = await request.json();

  if (!VALID_DIRECTIONS.has(body?.direction)) {
    return bffValidationError("direction must be one of: left, right, up.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/matches/${matchId}/swipe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction: body.direction }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }

  // Backend returns the full swipe record, but the client only needs to
  // confirm which direction was recorded (matches api-client.ts's submitSwipe return shape).
  return bffSuccess({ direction: body.direction as string });
}
