import { NextRequest } from "next/server";
import { toBackendOptOutRequest } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffSuccess,
  bffValidationError,
  backendFailureResponse,
  handleBackendJson,
} from "@/src/lib/bff-response";
import { isMockMode } from "@/src/lib/mocks/enabled";
import { OptOutInput } from "@/src/lib/types";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as OptOutInput;

  if (!body.identifier?.trim()) {
    return bffValidationError("Identifier is required.");
  }

  if (isMockMode()) {
    return bffSuccess({ status: "accepted" as const }, 202);
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/opt-out", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toBackendOptOutRequest(body)),
    });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }

  return handleBackendJson(backendResponse, () => ({ status: "accepted" as const }), 202);
}
