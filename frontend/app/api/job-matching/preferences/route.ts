import { NextRequest } from "next/server";
import {
  BackendJobPreferencesResponse,
  mapBackendJobPreferencesToFrontend,
  toBackendJobPreferencesRequest,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { CandidateJobPreferences } from "@/src/lib/types";

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/job-matching/preferences");
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendJobPreferencesResponse) =>
    mapBackendJobPreferencesToFrontend(payload),
  );
}

export async function PUT(request: NextRequest) {
  const body = (await request.json()) as Partial<CandidateJobPreferences>;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/job-matching/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toBackendJobPreferencesRequest(body)),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendJobPreferencesResponse) =>
    mapBackendJobPreferencesToFrontend(payload),
  );
}
