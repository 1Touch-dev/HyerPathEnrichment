import { NextRequest } from "next/server";
import {
  BackendJobResponse,
  hasIdentifier,
  mapBackendJobToFrontend,
  parseEnrichmentInput,
  toBackendEnrichmentRequest,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffSuccess,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";
import { isMockMode } from "@/src/lib/mocks/enabled";
import { createMockJobWithLifecycle } from "@/src/lib/mocks/mock-jobs";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as Parameters<typeof parseEnrichmentInput>[0];
  const input = parseEnrichmentInput(body);

  if (!hasIdentifier(input)) {
    return bffValidationError("At least one identifier is required.");
  }

  if (isMockMode()) {
    const job = createMockJobWithLifecycle(input);
    return bffSuccess(job, 202);
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/enrich", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toBackendEnrichmentRequest(input)),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson<BackendJobResponse, ReturnType<typeof mapBackendJobToFrontend>>(
    backendResponse,
    (payload) => mapBackendJobToFrontend(payload, input),
    202,
  );
}
