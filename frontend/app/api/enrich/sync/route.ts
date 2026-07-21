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
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as Parameters<typeof parseEnrichmentInput>[0];
  const input = parseEnrichmentInput(body);

  if (!hasIdentifier(input)) {
    return bffValidationError("At least one identifier is required.");
  }

  if (input.requestedTiers.includes("tier1")) {
    return bffValidationError(
      "Tier 1 is not available in sync mode. Use async enrichment or remove tier1.",
    );
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/enrich/sync", {
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
    200,
  );
}
