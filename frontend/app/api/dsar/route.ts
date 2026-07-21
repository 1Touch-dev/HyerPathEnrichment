import { NextRequest } from "next/server";
import {
  BackendDsarResponse,
  mapBackendDsarResponse,
  toBackendDsarRequest,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffSuccess,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";
import { isMockMode } from "@/src/lib/mocks/enabled";
import { DsarInput, DsarResponse } from "@/src/lib/types";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as DsarInput;

  if (!body.identifier?.trim()) {
    return bffValidationError("Identifier is required.");
  }

  if (!body.requestType) {
    return bffValidationError("Request type is required.");
  }

  if (isMockMode()) {
    const now = new Date().toISOString();
    const mock: DsarResponse = {
      id: `mock-dsar-${Date.now()}`,
      status: "completed",
      requestType: body.requestType,
      createdAt: now,
      completedAt: now,
      summary: {
        jobs_matched: 0,
        assets_purged: 0,
        suppressed: body.requestType === "deletion",
        mock: true,
      },
    };
    return bffSuccess(mock, 201);
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/dsar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toBackendDsarRequest(body)),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson<BackendDsarResponse, DsarResponse>(
    backendResponse,
    mapBackendDsarResponse,
    201,
  );
}
