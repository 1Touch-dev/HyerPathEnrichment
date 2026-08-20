import { NextRequest } from "next/server";
import {
  BackendInterviewScheduleResponse,
  mapBackendInterviewSchedule,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  bffSuccess,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;
  const body = (await request.json()) as {
    scheduled_at?: string;
    duration_minutes?: number;
    notes?: string | null;
  };

  if (!body.scheduled_at || typeof body.scheduled_at !== "string") {
    return bffValidationError("scheduled_at must be an ISO datetime string.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/interviews/matches/${matchId}/schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scheduled_at: body.scheduled_at,
        duration_minutes: body.duration_minutes ?? 60,
        notes: body.notes ?? null,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendInterviewScheduleResponse) =>
    mapBackendInterviewSchedule(payload),
  );
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/interviews/matches/${matchId}/schedule`);
  } catch {
    return bffServiceUnavailable();
  }

  // Backend returns `null` (200, `data: null`) when no interview is scheduled yet —
  // this is the expected common case (§15.5), not an error, so it must pass through
  // as-is rather than being coerced into a failure.
  return handleBackendJson(backendResponse, (payload: BackendInterviewScheduleResponse | null) =>
    payload ? mapBackendInterviewSchedule(payload) : null,
  );
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/interviews/matches/${matchId}/schedule`, {
      method: "DELETE",
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
