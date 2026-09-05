import { NextRequest } from "next/server";
import { BackendTrackedMatchResponse, mapBackendTrackedMatchItem } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";
import type { ApplicationStatus } from "@/src/lib/types";

const VALID_STATUSES: ApplicationStatus[] = [
  "new",
  "applied",
  "replied",
  "interview",
  "offer",
  "rejected",
];

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;
  const body = (await request.json()) as { application_status?: string };

  if (
    !body.application_status ||
    !VALID_STATUSES.includes(body.application_status as ApplicationStatus)
  ) {
    return bffValidationError(`application_status must be one of: ${VALID_STATUSES.join(", ")}.`);
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/application-tracker/matches/${matchId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application_status: body.application_status }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendTrackedMatchResponse) =>
    mapBackendTrackedMatchItem(payload),
  );
}
