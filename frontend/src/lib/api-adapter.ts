import {
  CandidateDocument,
  CandidateDocumentDetail,
  CandidateJobPreferences,
  CvData,
  DocumentJobStatus,
  DocumentSearchResponse,
  DocumentSearchResult,
  DocumentType,
  DocumentUploadResult,
  Dossier,
  EnrichmentInput,
  EnrichmentJob,
  HealthStatus,
  JobListItem,
  JobListResponse,
  JobMatch,
  JobMatchListResponse,
  JobStatus,
  OptOutInput,
  RequestedTier,
  DsarInput,
  DsarResponse,
  SignalListItem,
  SignalListResponse,
} from "@/src/lib/types";
import type {
  BackendCVDataResponse,
  BackendDocumentDetailResponse,
  BackendDocumentMetadata,
  BackendDocumentUploadResponse,
  BackendDossier,
  BackendDsarResponse,
  BackendHealthResponse,
  BackendJobListItem,
  BackendJobListResponse,
  BackendJobMatchListResponse,
  BackendJobMatchResponse,
  BackendJobPreferencesResponse,
  BackendJobResponse,
  BackendJobStatusResponse,
  BackendSearchResponse,
  BackendSearchResult,
  BackendSignalListItem,
  BackendSignalListResponse,
} from "@/src/lib/generated/api-schemas";

export type {
  BackendCVDataResponse,
  BackendDocumentDetailResponse,
  BackendDocumentMetadata,
  BackendDocumentUploadResponse,
  BackendDsarResponse,
  BackendHealthResponse,
  BackendJobListResponse,
  BackendJobMatchListResponse,
  BackendJobMatchResponse,
  BackendJobPreferencesResponse,
  BackendJobResponse,
  BackendJobStatusResponse,
  BackendSearchResponse,
  BackendSignalListResponse,
} from "@/src/lib/generated/api-schemas";

function normalizeJobStatus(status: string): JobStatus {
  if (
    status === "queued" ||
    status === "running" ||
    status === "completed" ||
    status === "completed_no_data" ||
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

function normalizeNullableFields<T extends Record<string, unknown>>(value: T): T {
  const normalized: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(value)) {
    normalized[key] = val === null ? undefined : val;
  }
  return normalized as T;
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
    business: dossier.business
      ? // Backend's BusinessProfile schema marks most optional fields `| null`;
        // the frontend type uses `| undefined` for "absent" — normalize at the
        // boundary. (Field names are otherwise passed through as-is here.)
        (normalizeNullableFields(dossier.business) as unknown as Dossier["business"])
      : undefined,
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
    createdAt: backendJob.created_at,
    updatedAt: backendJob.updated_at,
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

export function mapBackendJobPreferencesToFrontend(
  raw: BackendJobPreferencesResponse,
): CandidateJobPreferences {
  return {
    userId: raw.user_id,
    sourceDocumentId: raw.source_document_id,
    desiredRoles: raw.desired_roles ?? [],
    desiredLocations: raw.desired_locations ?? [],
    remotePreference: raw.remote_preference ?? null,
    salaryMin: raw.salary_min ?? null,
    salaryMax: raw.salary_max ?? null,
    salaryCurrency: raw.salary_currency,
    notificationChannels: raw.notification_channels ?? [],
    webhookUrl: raw.webhook_url ?? null,
    digestFrequency: raw.digest_frequency,
    isScanEnabled: raw.is_scan_enabled,
    lastScannedAt: raw.last_scanned_at,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function mapBackendJobMatchItem(item: BackendJobMatchResponse): JobMatch {
  return {
    matchId: item.match_id,
    jobPostingId: item.job_posting_id,
    title: item.title,
    company: item.company,
    location: item.location,
    remote: item.remote,
    source: item.source,
    sourceUrl: item.source_url,
    salaryMin: item.salary_min,
    salaryMax: item.salary_max,
    salaryCurrency: item.salary_currency,
    overallScore: item.overall_score,
    scoreBreakdown: item.score_breakdown,
    explanation: item.explanation,
    isNew: item.is_new,
    viewedAt: item.viewed_at,
    feedback: item.feedback,
    createdAt: item.created_at,
  };
}

export function mapBackendJobMatchListToFrontend(
  response: BackendJobMatchListResponse,
): JobMatchListResponse {
  return {
    matches: response.matches.map(mapBackendJobMatchItem),
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
    job_title: input.jobTitle || null,
    job_location: input.jobLocation || null,
    job_country: input.jobCountry || null,
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

export function toBackendJobPreferencesRequest(input: Partial<CandidateJobPreferences>) {
  return {
    desired_roles: input.desiredRoles,
    desired_locations: input.desiredLocations,
    remote_preference: input.remotePreference ?? null,
    salary_min: input.salaryMin ?? null,
    salary_max: input.salaryMax ?? null,
    salary_currency: input.salaryCurrency,
    notification_channels: input.notificationChannels,
    webhook_url: input.webhookUrl ?? null,
    digest_frequency: input.digestFrequency,
    is_scan_enabled: input.isScanEnabled,
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

export function mapBackendDocumentMetadata(raw: BackendDocumentMetadata): CandidateDocument {
  return {
    documentId: raw.document_id,
    documentType: raw.document_type as DocumentType,
    originalFilename: raw.original_filename,
    fileSizeBytes: raw.file_size_bytes,
    processingStatus: raw.processing_status,
    createdAt: raw.created_at,
  };
}

export function mapBackendDocumentList(raw: BackendDocumentMetadata[]): CandidateDocument[] {
  return raw.map(mapBackendDocumentMetadata);
}

export function mapBackendDocumentDetail(
  raw: BackendDocumentDetailResponse,
): CandidateDocumentDetail {
  return {
    documentId: raw.document_id,
    documentType: raw.document_type as DocumentType,
    originalFilename: raw.original_filename,
    fileSizeBytes: raw.file_size_bytes,
    processingStatus: raw.processing_status,
    rawText: raw.raw_text ?? null,
    extractedData: raw.extracted_data ?? null,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function mapBackendDocumentUploadResponse(
  raw: BackendDocumentUploadResponse,
): DocumentUploadResult {
  return {
    jobId: raw.job_id,
    documentId: raw.document_id,
    message: raw.message,
  };
}

export function mapBackendDocumentJobStatus(raw: BackendJobStatusResponse): DocumentJobStatus {
  return {
    jobId: raw.job_id,
    status: raw.status,
    progress: raw.progress,
    documentId: raw.document_id ?? null,
    result: raw.result ?? null,
    error: raw.error ?? null,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function mapBackendCvData(raw: BackendCVDataResponse): CvData {
  return {
    documentId: raw.document_id,
    extractedData: raw.extracted_data ?? {},
    rawText: raw.raw_text ?? null,
    processingStatus: raw.processing_status,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function mapBackendDocumentSearchResult(raw: BackendSearchResult): DocumentSearchResult {
  return {
    documentId: raw.document_id,
    similarityScore: raw.similarity_score,
    cvData: raw.cv_data ?? {},
    excerpt: raw.excerpt,
  };
}

export function mapBackendDocumentSearchResponse(
  raw: BackendSearchResponse,
): DocumentSearchResponse {
  return {
    results: (raw.results ?? []).map(mapBackendDocumentSearchResult),
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
    jobTitle: body.jobTitle?.trim() || "",
    jobLocation: body.jobLocation?.trim() || "",
    jobCountry: body.jobCountry?.trim() || "",
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
