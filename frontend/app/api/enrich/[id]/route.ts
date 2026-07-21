import { NextRequest } from "next/server";
import { BackendJobResponse, mapBackendJobToFrontend } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffError,
  bffServiceUnavailable,
  bffSuccess,
  handleBackendJson,
} from "@/src/lib/bff-response";
import { EnrichmentInput } from "@/src/lib/types";
import { isMockMode } from "@/src/lib/mocks/enabled";
import { getMockJob } from "@/src/lib/mocks/mock-jobs";

export async function GET(_request: NextRequest, { params }: { params: { id: string } }) {
  if (isMockMode()) {
    const job = getMockJob(params.id);
    if (!job) {
      return bffError("NOT_FOUND", "Job not found.", 404);
    }
    return bffSuccess(job);
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/enrich/${params.id}`);
  } catch {
    return bffServiceUnavailable();
  }

  const result = await handleBackendJson<
    BackendJobResponse,
    ReturnType<typeof mapBackendJobToFrontend>
  >(backendResponse, (backendJob) => {
    const input: EnrichmentInput = {
      email: "",
      linkedinUrl: "",
      username: "",
      company: "",
      business: "",
      jobSearch: "",
      requestedTiers: [],
    };

    const metadata = backendJob.dossier?.metadata as Record<string, unknown> | undefined;
    if (metadata) {
      const tiers = metadata.requested_tiers ?? metadata.requestedTiers;
      if (Array.isArray(tiers)) {
        input.requestedTiers = tiers.filter(
          (tier): tier is EnrichmentInput["requestedTiers"][number] =>
            tier === "tier1" || tier === "tier2" || tier === "tier3" || tier === "tier4",
        );
      }
      const summary = metadata.identifier_summary ?? metadata.identifierSummary;
      if (typeof summary === "string" && summary) {
        input.username = summary;
      }
    }

    return mapBackendJobToFrontend(backendJob, input);
  });

  return result;
}
