import {
  Dossier,
  EnrichmentInput,
  EnrichmentJob,
  HealthStatus,
  JobListItem,
  JobListResponse,
  JobStatus,
  OptOutInput,
  RequestedTier,
  DsarInput,
  DsarResponse,
  SignalListItem,
  SignalListResponse,
} from "@/src/lib/types";
import type {
  BackendDossier,
  BackendDsarResponse,
  BackendHealthResponse,
  BackendJobListItem,
  BackendJobListResponse,
  BackendJobResponse,
  BackendSignalListItem,
  BackendSignalListResponse,
} from "@/src/lib/generated/api-schemas";

export type {
  BackendDsarResponse,
  BackendHealthResponse,
  BackendJobListResponse,
  BackendJobResponse,
  BackendSignalListResponse,
} from "@/src/lib/generated/api-schemas";

function normalizeJobStatus(status: string): JobStatus {
  if (
    status === "queued" ||
    status === "running" ||
    status === "completed" ||
    status === "failed" ||
    status === "suppressed"
  ) {
    return status;
  }
  return "failed";
}

function readMetadataString(
  metadata: Record<string, unknown>,
  snakeKey: string,
  camelKey: string,
): string {
  const value = metadata[snakeKey] ?? metadata[camelKey];
  return typeof value === "string" ? value : "";
}

function readMetadataTiers(metadata: Record<string, unknown>): RequestedTier[] {
  const value = metadata.requested_tiers ?? metadata.requestedTiers;
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (tier): tier is RequestedTier =>
      tier === "tier1" || tier === "tier2" || tier === "tier3" || tier === "tier4",
  );
}

function mapGithub(github: BackendDossier["github"]): Dossier["github"] | undefined {
  if (!github || typeof github !== "object") {
    return undefined;
  }

  const raw = github as Record<string, unknown>;
  const organizations = raw.organizations;
  const publicCommits = raw.public_commits ?? raw.publicCommits;

  return {
    profile: typeof raw.profile === "string" ? raw.profile : undefined,
    organizations: Array.isArray(organizations)
      ? organizations.filter((org): org is string => typeof org === "string")
      : [],
    publicCommits: typeof publicCommits === "number" ? publicCommits : 0,
  };
}

function normalizeHandleMetadata(
  metadata: Record<string, unknown> | undefined,
): Record<string, string | number | boolean> | undefined {
  if (!metadata) {
    return undefined;
  }
  const normalized: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(metadata)) {
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      normalized[key] = value;
    }
  }
  return Object.keys(normalized).length > 0 ? normalized : undefined;
}

function mapDossier(dossier: BackendDossier): Dossier {
  const metadata = dossier.metadata ?? {};

  return {
    photo: dossier.photo
      ? {
          source: dossier.photo.source,
          assetUrl: dossier.photo.asset_url,
          capturedAt:
            typeof dossier.photo.captured_at === "string"
              ? dossier.photo.captured_at
              : String(dossier.photo.captured_at ?? ""),
          confidence: dossier.photo.confidence,
        }
      : undefined,
    handles: (dossier.handles ?? []).map((handle) => ({
      platform: handle.platform,
      username: handle.username,
      profileUrl: handle.profile_url,
      confidence: handle.confidence,
      metadata: normalizeHandleMetadata(handle.metadata),
    })),
    emails: dossier.emails ?? [],
    verifiedEmails: (dossier.verified_emails ?? []).map((email) => ({
      value: email.value,
      status: email.status as "verified" | "risky" | "unknown" | "disposable",
      confidence: email.confidence,
      source: email.source,
    })),
    github: mapGithub(dossier.github),
    coworkers: dossier.coworkers ?? [],
    jobs: dossier.jobs ?? [],
    business: dossier.business ?? undefined,
    confidence: dossier.confidence ?? [],
    sources: dossier.sources ?? [],
    metadata: {
      generatedAt: readMetadataString(metadata, "generated_at", "generatedAt"),
      pipelineId: readMetadataString(metadata, "pipeline_id", "pipelineId"),
      requestedTiers: readMetadataTiers(metadata),
      identifierSummary: readMetadataString(metadata, "identifier_summary", "identifierSummary"),
    },
  };
}

function identifierSummaryFromPayload(payload: Record<string, unknown> | undefined): string {
  if (!payload) {
    return "";
  }
  const values = [
    payload.email,
    payload.linkedin_url,
    payload.linkedinUrl,
    payload.username,
    payload.company,
    payload.business,
    payload.job_search,
    payload.jobSearch,
  ].filter((v): v is string => typeof v === "string" && v.length > 0);
  return values.join(" • ");
}

function tiersFromPayload(payload: Record<string, unknown> | undefined): RequestedTier[] {
  if (!payload) {
    return [];
  }
  const value = payload.requested_tiers ?? payload.requestedTiers;
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (tier): tier is RequestedTier =>
      tier === "tier1" || tier === "tier2" || tier === "tier3" || tier === "tier4",
  );
}

export function mapBackendJobToFrontend(
  backendJob: BackendJobResponse,
  input: EnrichmentInput,
): EnrichmentJob {
  return {
    id: backendJob.id,
    status: normalizeJobStatus(backendJob.status),
    input,
    dossier: mapDossier(backendJob.dossier),
    error: backendJob.error,
  };
}

export function mapBackendJobListItem(item: BackendJobListItem): JobListItem {
  const payload = item.request_payload;
  return {
    id: item.id,
    status: normalizeJobStatus(item.status),
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    identifierSummary: item.identifier_summary || identifierSummaryFromPayload(payload),
    requestedTiers: tiersFromPayload(payload),
  };
}

export function mapBackendJobListToFrontend(response: BackendJobListResponse): JobListResponse {
  return {
    jobs: response.jobs.map(mapBackendJobListItem),
    total: response.total,
    limit: response.limit,
    offset: response.offset,
  };
}

export function mapBackendSignalListItem(item: BackendSignalListItem): SignalListItem {
  return {
    id: item.id,
    source: item.source,
    watchId: item.watch_id,
    title: item.title,
    url: item.url,
    timestamp: item.timestamp,
    createdAt: item.created_at,
  };
}

export function mapBackendSignalListToFrontend(
  response: BackendSignalListResponse,
): SignalListResponse {
  return {
    signals: response.signals.map(mapBackendSignalListItem),
    total: response.total,
    limit: response.limit,
    offset: response.offset,
  };
}

export function toBackendEnrichmentRequest(input: EnrichmentInput) {
  return {
    email: input.email || null,
    linkedin_url: input.linkedinUrl || null,
    username: input.username || null,
    company: input.company || null,
    business: input.business || null,
    job_search: input.jobSearch || null,
    requested_tiers: input.requestedTiers,
  };
}

export function toBackendOptOutRequest(input: OptOutInput) {
  return {
    identifier: input.identifier,
    reason: input.reason || null,
  };
}

export function toBackendDsarRequest(input: DsarInput) {
  return {
    identifier: input.identifier,
    request_type: input.requestType,
    notes: input.notes || null,
  };
}

export function mapBackendDsarResponse(response: BackendDsarResponse): DsarResponse {
  return {
    id: response.id,
    status: response.status,
    requestType: response.request_type as DsarInput["requestType"],
    createdAt: response.created_at,
    completedAt: response.completed_at,
    summary: response.summary ?? {},
  };
}

export function mapBackendHealth(response: BackendHealthResponse): HealthStatus {
  return {
    status: response.status,
    service: response.service ?? "hyrepath-enrichment",
  };
}

export function parseEnrichmentInput(body: Partial<EnrichmentInput>): EnrichmentInput {
  return {
    email: body.email?.trim() || "",
    linkedinUrl: body.linkedinUrl?.trim() || "",
    username: body.username?.trim() || "",
    company: body.company?.trim() || "",
    business: body.business?.trim() || "",
    jobSearch: body.jobSearch?.trim() || "",
    requestedTiers: body.requestedTiers?.length
      ? body.requestedTiers
      : ["tier1", "tier2", "tier3", "tier4"],
  };
}

export function hasIdentifier(input: EnrichmentInput): boolean {
  return Boolean(
    input.email ||
    input.linkedinUrl ||
    input.username ||
    input.company ||
    input.business ||
    input.jobSearch,
  );
}
