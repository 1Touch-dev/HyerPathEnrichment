import {
  AdminAuditLogEntry,
  AdminAuditLogListResponse,
  AdminJobPosting,
  AdminJobPostingListResponse,
  AdminReviewQueueDetail,
  AdminReviewQueueItem,
  AdminReviewQueueListResponse,
  AdminDocument,
  AdminDocumentListResponse,
  AdminRoleWithPermissions,
  AdminUser,
  AdminUserListResponse,
  BackendAdminJobPostingListResponse,
  BackendAdminJobPostingResponse,
  BackendAdminReviewQueueDetail,
  BackendAdminReviewQueueItem,
  BackendAdminReviewQueueListResponse,
  BackendAdminDocumentListResponse,
  BackendAdminDocumentResponse,
  CandidateDocument,
  CandidateDocumentDetail,
  CandidateJobPreferences,
  CvChatSession,
  CvCompleteness,
  CvData,
  CvFeedbackReport,
  Dossier,
  DocumentJobStatus,
  DocumentSearchResponse,
  DocumentSearchResult,
  DocumentSummary,
  DocumentType,
  DocumentUploadResult,
  EnrichmentInput,
  EnrichmentJob,
  FailedJob,
  FeatureFlag,
  HealthStatus,
  ImpersonationStatus,
  JobListItem,
  JobListResponse,
  JobMatch,
  JobMatchAnalytics,
  JobMatchListResponse,
  JobStatus,
  MfaEnrollResult,
  MfaStatus,
  OptOutInput,
  OutreachMessage,
  PortfolioItem,
  PortfolioProfile,
  PublicPortfolioProfile,
  QueueSnapshot,
  RequestedTier,
  DsarInput,
  DsarResponse,
  SignalListItem,
  SignalListResponse,
  SwipeDeck,
  SystemHealthSnapshot,
} from "@/src/lib/types";
import type {
  BackendAdminAuditLogEntryResponse,
  BackendAdminAuditLogListResponse,
  BackendAdminUserListResponse,
  BackendAdminUserResponse,
  BackendCVDataResponse,
  BackendDocumentDetailResponse,
  BackendDocumentMetadata,
  BackendDocumentUploadResponse,
  BackendDossier,
  BackendDsarResponse,
  BackendFailedJobResponse,
  BackendFeatureFlagResponse,
  BackendHealthResponse,
  BackendImpersonationStartResponse,
  BackendImpersonationStatusResponse,
  BackendJobListItem,
  BackendJobListResponse,
  BackendJobMatchAnalyticsResponse,
  BackendJobMatchListResponse,
  BackendJobMatchResponse,
  BackendJobPreferencesResponse,
  BackendJobResponse,
  BackendJobStatusResponse,
  BackendMfaEnrollResponse,
  BackendMfaStatusResponse,
  BackendQueueSnapshotResponse,
  BackendRoleWithPermissionsResponse,
  BackendSearchResponse,
  BackendSearchResult,
  BackendSignalListItem,
  BackendSignalListResponse,
  BackendSystemHealthResponse,
} from "@/src/lib/generated/api-schemas";

export type {
  BackendAdminAuditLogEntryResponse,
  BackendAdminAuditLogListResponse,
  BackendAdminUserListResponse,
  BackendAdminUserResponse,
  BackendAssignRoleRequest,
  BackendCVDataResponse,
  BackendDocumentDetailResponse,
  BackendDocumentMetadata,
  BackendDocumentUploadResponse,
  BackendDsarResponse,
  BackendFailedJobResponse,
  BackendFeatureFlagResponse,
  BackendHealthResponse,
  BackendImpersonationStartRequest,
  BackendImpersonationStartResponse,
  BackendImpersonationStatusResponse,
  BackendJobListResponse,
  BackendJobMatchAnalyticsResponse,
  BackendJobMatchListResponse,
  BackendJobMatchResponse,
  BackendJobPreferencesResponse,
  BackendJobResponse,
  BackendJobStatusResponse,
  BackendMfaEnrollResponse,
  BackendMfaStatusResponse,
  BackendMfaVerifyRequest,
  BackendQueueSnapshotResponse,
  BackendQueuesOverviewResponse,
  BackendRoleWithPermissionsResponse,
  BackendSearchResponse,
  BackendSignalListResponse,
  BackendSystemHealthResponse,
  BackendUpdateUserStatusRequest,
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

// Admin module (phase2_admin_module.md §11.3)

export function mapBackendAdminUser(raw: BackendAdminUserResponse): AdminUser {
  return {
    id: raw.id,
    email: raw.email,
    firstName: raw.first_name,
    lastName: raw.last_name,
    isActive: raw.is_active,
    isVerified: raw.is_verified,
    isSuperuser: raw.is_superuser,
    roleId: raw.role_id,
    roleName: raw.role_name,
    mfaEnabled: raw.mfa_enabled,
    createdAt: raw.created_at,
    deletedAt: raw.deleted_at,
  };
}

export function mapBackendAdminUserList(raw: BackendAdminUserListResponse): AdminUserListResponse {
  return {
    items: raw.items.map(mapBackendAdminUser),
    nextCursor: raw.next_cursor,
    hasMore: raw.has_more,
  };
}

export function mapBackendAdminReviewQueueItem(
  raw: BackendAdminReviewQueueItem,
): AdminReviewQueueItem {
  return {
    id: raw.id,
    resourceType: raw.resource_type,
    resourceId: raw.resource_id,
    status: raw.status,
    flagReason: raw.flag_reason,
    flagSource: raw.flag_source,
    flaggedAt: raw.flagged_at,
    reviewedBy: raw.reviewed_by,
    reviewedAt: raw.reviewed_at,
    reviewNotes: raw.review_notes,
  };
}

export function mapBackendAdminReviewQueueList(
  raw: BackendAdminReviewQueueListResponse,
): AdminReviewQueueListResponse {
  return {
    items: raw.items.map(mapBackendAdminReviewQueueItem),
    nextCursor: raw.next_cursor,
    hasMore: raw.has_more,
  };
}

export function mapBackendAdminReviewQueueDetail(
  raw: BackendAdminReviewQueueDetail,
): AdminReviewQueueDetail {
  return {
    item: mapBackendAdminReviewQueueItem(raw.item),
    resolvedResource: raw.resolved_resource,
  };
}

export function mapBackendAdminJobPosting(raw: BackendAdminJobPostingResponse): AdminJobPosting {
  return {
    id: raw.id,
    title: raw.title,
    company: raw.company,
    location: raw.location,
    remote: raw.remote,
    source: raw.source,
    sourceUrl: raw.source_url,
    salaryMin: raw.salary_min,
    salaryMax: raw.salary_max,
    salaryCurrency: raw.salary_currency,
    postedAt: raw.posted_at,
    firstSeenAt: raw.first_seen_at,
    lastSeenAt: raw.last_seen_at,
    isActive: raw.is_active,
    moderationStatus: raw.moderation_status,
    moderatedBy: raw.moderated_by,
    moderatedAt: raw.moderated_at,
  };
}

export function mapBackendAdminJobPostingList(
  raw: BackendAdminJobPostingListResponse,
): AdminJobPostingListResponse {
  return {
    items: raw.items.map(mapBackendAdminJobPosting),
    nextCursor: raw.next_cursor,
    hasMore: raw.has_more,
  };
}

export function mapBackendAdminDocument(raw: BackendAdminDocumentResponse): AdminDocument {
  return {
    id: raw.id,
    userId: raw.user_id,
    documentType: raw.document_type,
    originalFilename: raw.original_filename,
    mimeType: raw.mime_type,
    fileSizeBytes: raw.file_size_bytes,
    processingStatus: raw.processing_status,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    deletedAt: raw.deleted_at,
  };
}

export function mapBackendAdminDocumentList(
  raw: BackendAdminDocumentListResponse,
): AdminDocumentListResponse {
  return {
    items: raw.items.map(mapBackendAdminDocument),
    nextCursor: raw.next_cursor,
    hasMore: raw.has_more,
  };
}

export function mapBackendAuditLogEntry(
  raw: BackendAdminAuditLogEntryResponse,
): AdminAuditLogEntry {
  return {
    id: raw.id,
    actorUserId: raw.actor_user_id,
    impersonatedBy: raw.impersonated_by,
    action: raw.action,
    targetType: raw.target_type,
    targetId: raw.target_id,
    before: raw.before,
    after: raw.after,
    ipAddress: raw.ip_address,
    capturedBy: raw.captured_by as AdminAuditLogEntry["capturedBy"],
    createdAt: raw.created_at,
  };
}

export function mapBackendAuditLogList(
  raw: BackendAdminAuditLogListResponse,
): AdminAuditLogListResponse {
  return {
    items: raw.items.map(mapBackendAuditLogEntry),
    nextCursor: raw.next_cursor,
    hasMore: raw.has_more,
  };
}

export function mapBackendFeatureFlag(raw: BackendFeatureFlagResponse): FeatureFlag {
  return {
    key: raw.key,
    enabled: raw.enabled,
    value: raw.value,
    description: raw.description,
    updatedBy: raw.updated_by,
    updatedAt: raw.updated_at,
  };
}

export function toBackendFeatureFlagRequest(input: Partial<FeatureFlag>) {
  return {
    enabled: input.enabled,
    value: input.value ?? null,
    description: input.description ?? null,
  };
}

export function mapBackendQueueSnapshot(raw: BackendQueueSnapshotResponse): QueueSnapshot {
  return {
    name: raw.name,
    priority: raw.priority,
    queuedCount: raw.queued_count,
    failedCount: raw.failed_count,
    oldestQueuedAgeSeconds: raw.oldest_queued_age_seconds,
    workersListening: raw.workers_listening,
  };
}

export function mapBackendSystemHealth(raw: BackendSystemHealthResponse): SystemHealthSnapshot {
  return {
    databaseOk: raw.database_ok,
    databaseLatencyMs: raw.database_latency_ms,
    redisOk: raw.redis_ok,
    redisLatencyMs: raw.redis_latency_ms,
    prometheusConfigured: raw.prometheus_configured,
    signals: raw.signals,
  };
}

export function mapBackendJobMatchAnalytics(
  raw: BackendJobMatchAnalyticsResponse,
): JobMatchAnalytics {
  return {
    totalPostings: raw.total_postings,
    totalMatches: raw.total_matches,
    postingsBySource: raw.postings_by_source,
    topCompanies: raw.top_companies as JobMatchAnalytics["topCompanies"],
    avgSalaryMin: raw.avg_salary_min,
    avgSalaryMax: raw.avg_salary_max,
    avgOverallScore: raw.avg_overall_score,
    computedAt: raw.computed_at,
    cacheHit: raw.cache_hit,
  };
}

// The four mappers below are not given verbatim in §11.3's code block (which only
// covers users/audit-logs/feature-flags/queues/system-health/analytics) but are
// needed by §11.4's roles, queues/{name}/failed, and mfa/impersonation BFF routes,
// which do have §11.2 frontend types (`AdminRoleWithPermissions`, `FailedJob`,
// `MfaStatus`, `MfaEnrollResult`, `ImpersonationStatus`) but no listed adapter —
// added here following the exact same `mapBackend*` naming/shape convention.

export function mapBackendRoleWithPermissions(
  raw: BackendRoleWithPermissionsResponse,
): AdminRoleWithPermissions {
  return {
    id: raw.id,
    name: raw.name,
    description: raw.description,
    isSystem: raw.is_system,
    permissions: raw.permissions.map((permission) => ({
      id: permission.id,
      resource: permission.resource,
      action: permission.action,
      description: permission.description,
    })),
  };
}

export function mapBackendFailedJob(raw: BackendFailedJobResponse): FailedJob {
  return {
    jobId: raw.job_id,
    queueName: raw.queue_name,
    funcName: raw.func_name,
    enqueuedAt: raw.enqueued_at,
    failedAt: raw.failed_at,
    excInfo: raw.exc_info,
  };
}

export function mapBackendMfaEnrollResult(raw: BackendMfaEnrollResponse): MfaEnrollResult {
  return {
    secret: raw.secret,
    provisioningUri: raw.provisioning_uri,
  };
}

export function mapBackendMfaStatus(raw: BackendMfaStatusResponse): MfaStatus {
  return {
    mfaEnabled: raw.mfa_enabled,
    mfaEnrolledAt: raw.mfa_enrolled_at,
  };
}

export function mapBackendImpersonationStatus(
  raw: BackendImpersonationStatusResponse,
): ImpersonationStatus {
  return {
    isImpersonating: raw.is_impersonating,
    adminUserId: raw.admin_user_id,
    adminEmail: raw.admin_email,
    targetUserId: raw.target_user_id,
    expiresAt: raw.expires_at,
  };
}

export function mapBackendImpersonationStart(raw: BackendImpersonationStartResponse) {
  return {
    targetUserId: raw.target_user_id,
    expiresAt: raw.expires_at,
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

// Module 2: Tinder-Style Job Board + CV Management (phase2_module2.md §11.3)
//
// The backend routes these adapt (CV completeness/chat/feedback, portfolio,
// job swipe, outreach — phase2_module2.md §8) do not exist yet, so
// `src/lib/generated/api-schemas.ts` has no generated schemas for them. The
// `Raw*Response` interfaces below are hand-declared placeholders mirroring
// §11.3's documented snake_case shapes; per this file's own convention
// (see `Backend*Response` imports above), they must be deleted and replaced
// with real `npm run openapi:gen` output once the backend routes exist —
// do not let these placeholders become permanent hand-maintained duplicates.

interface RawCvCompletenessResponse {
  document_id: string;
  completeness_score: number;
  missing_fields: string[];
  has_active_chat_session: boolean;
}

interface RawCvChatMessageResponse {
  id: string;
  role: "assistant" | "user";
  content: string;
  created_at: string;
}

interface RawCvChatSessionResponse {
  session_id: string;
  status: "active" | "completed" | "abandoned";
  missing_fields_at_start: string[];
  fields_resolved: string[];
  messages: RawCvChatMessageResponse[];
}

/**
 * Mirrors the backend's real `CvFeedbackResponse` (backend/app/modules/documents/schemas.py)
 * — no `status` field exists on this response; a `CvFeedbackReport` row only exists once
 * generation is fully complete (backend/app/workers/tasks/cv_improvement.py never inserts
 * an interim "pending" row). "Is generation still running?" is answered by polling the real
 * job-status endpoint (`GET /api/documents/jobs/{job_id}`), not by a fake status on this type.
 */
interface RawCvFeedbackReportResponse {
  report_id: string;
  document_id: string;
  target_role: string | null;
  ats_score: number;
  strengths: string[];
  improvements: string[];
  rewritten_bullets: { original: string; rewritten: string; rationale: string }[];
  accepted_bullet_indices: number[];
  created_at: string;
}

/** Mirrors the backend's `JobStatusResponse` (backend/app/modules/documents/schemas.py). */
interface RawJobStatusResponse {
  job_id: string;
  status: string;
  progress: number;
  document_id: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

/** Mirrors the backend's `DocumentMetadata` (backend/app/modules/documents/schemas.py). */
interface RawDocumentMetadataResponse {
  document_id: string;
  document_type: string;
  original_filename: string;
  file_size_bytes: number;
  processing_status: string;
  created_at: string;
}

interface RawPortfolioItemResponse {
  item_id: string;
  item_type: "github" | "live_demo" | "case_study" | "other";
  title: string;
  description: string | null;
  url: string;
  display_order: number;
}

interface RawPortfolioProfileResponse {
  profile_id: string;
  user_id: string;
  slug: string;
  display_name: string | null;
  headline: string | null;
  bio: string | null;
  is_published: boolean;
  public_url: string;
  items: RawPortfolioItemResponse[];
  created_at: string;
  updated_at: string;
}

interface RawPublicPortfolioProfileResponse {
  slug: string;
  display_name: string | null;
  headline: string | null;
  bio: string | null;
  items: RawPortfolioItemResponse[];
}

/**
 * Mirrors the backend's real `SwipeableMatchResponse` (backend/app/modules/job_swipe/schemas.py)
 * — that schema has no `score_breakdown` field (unlike Module 1's `JobMatch`, which does have
 * one from a different backend model). Nothing in `frontend/features/job-swipe/` renders a score
 * breakdown, so it is intentionally omitted here rather than kept as a dead optional field.
 */
interface RawSwipeCardResponse {
  match_id: string;
  job_posting_id: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  overall_score: number;
  explanation: string | null;
}

interface RawSwipeDeckResponse {
  cards: RawSwipeCardResponse[];
  has_more: boolean;
}

interface RawOutreachMessageResponse {
  message_id: string;
  company_name: string;
  recipient_role_title: string | null;
  subject: string;
  body: string;
  status: "draft" | "sent";
  sent_at: string | null;
  created_at: string;
}

export function adaptCvCompleteness(raw: RawCvCompletenessResponse): CvCompleteness {
  return {
    documentId: raw.document_id,
    completenessScore: raw.completeness_score,
    missingFields: raw.missing_fields,
    hasActiveChatSession: raw.has_active_chat_session,
  };
}

export function adaptCvChatSession(raw: RawCvChatSessionResponse): CvChatSession {
  return {
    sessionId: raw.session_id,
    status: raw.status,
    missingFieldsAtStart: raw.missing_fields_at_start,
    fieldsResolved: raw.fields_resolved,
    messages: raw.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      createdAt: m.created_at,
    })),
  };
}

export function adaptCvFeedbackReport(raw: RawCvFeedbackReportResponse): CvFeedbackReport {
  return {
    reportId: raw.report_id,
    documentId: raw.document_id,
    targetRole: raw.target_role,
    atsScore: raw.ats_score,
    strengths: raw.strengths,
    improvements: raw.improvements,
    rewrittenBullets: raw.rewritten_bullets,
    acceptedBulletIndices: raw.accepted_bullet_indices,
    createdAt: raw.created_at,
  };
}

export function adaptDocumentJobStatus(raw: RawJobStatusResponse): DocumentJobStatus {
  return {
    jobId: raw.job_id,
    status: raw.status,
    progress: raw.progress,
    documentId: raw.document_id,
    result: raw.result,
    error: raw.error,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function adaptDocumentSummary(raw: RawDocumentMetadataResponse): DocumentSummary {
  return {
    documentId: raw.document_id,
    documentType: raw.document_type,
    originalFilename: raw.original_filename,
    fileSizeBytes: raw.file_size_bytes,
    processingStatus: raw.processing_status,
    createdAt: raw.created_at,
  };
}

const PORTFOLIO_ITEM_TYPE_FROM_BACKEND: Record<
  RawPortfolioItemResponse["item_type"],
  PortfolioItem["itemType"]
> = {
  github: "github_repo",
  live_demo: "live_demo",
  case_study: "case_study",
  other: "other_link",
};

const PORTFOLIO_ITEM_TYPE_TO_BACKEND: Record<
  PortfolioItem["itemType"],
  RawPortfolioItemResponse["item_type"]
> = {
  github_repo: "github",
  live_demo: "live_demo",
  case_study: "case_study",
  other_link: "other",
};

/**
 * Backend's `PortfolioItemRequest.item_type` is `"github"|"live_demo"|"case_study"|"other"`
 * (backend/app/modules/portfolio/schemas.py); the frontend-facing `PortfolioItem.itemType`
 * uses `"github_repo"|"live_demo"|"case_study"|"other_link"` instead. Used by the outgoing
 * `POST /api/portfolio/items` BFF route to translate the request body.
 */
export function toBackendPortfolioItemType(
  itemType: PortfolioItem["itemType"],
): RawPortfolioItemResponse["item_type"] {
  return PORTFOLIO_ITEM_TYPE_TO_BACKEND[itemType] ?? "other";
}

export function adaptPortfolioItem(raw: RawPortfolioItemResponse): PortfolioItem {
  return {
    itemId: raw.item_id,
    itemType: PORTFOLIO_ITEM_TYPE_FROM_BACKEND[raw.item_type] ?? "other_link",
    title: raw.title,
    description: raw.description,
    url: raw.url,
    displayOrder: raw.display_order,
  };
}

export function adaptPortfolioProfile(raw: RawPortfolioProfileResponse): PortfolioProfile {
  return {
    profileId: raw.profile_id,
    userId: raw.user_id,
    slug: raw.slug,
    displayName: raw.display_name,
    headline: raw.headline,
    summary: raw.bio,
    isPublished: raw.is_published,
    publicUrl: raw.public_url,
    items: raw.items.map(adaptPortfolioItem),
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function adaptPublicPortfolioProfile(
  raw: RawPublicPortfolioProfileResponse,
): PublicPortfolioProfile {
  return {
    slug: raw.slug,
    displayName: raw.display_name,
    headline: raw.headline,
    summary: raw.bio,
    items: raw.items.map(adaptPortfolioItem),
  };
}

export function adaptSwipeDeck(raw: RawSwipeDeckResponse): SwipeDeck {
  return {
    cards: raw.cards.map((c) => ({
      matchId: c.match_id,
      jobPostingId: c.job_posting_id,
      title: c.title,
      company: c.company,
      location: c.location,
      remote: c.remote,
      salaryMin: c.salary_min,
      salaryMax: c.salary_max,
      salaryCurrency: c.salary_currency,
      overallScore: c.overall_score,
      explanation: c.explanation,
    })),
    hasMore: raw.has_more,
  };
}

export function adaptOutreachMessage(raw: RawOutreachMessageResponse): OutreachMessage {
  return {
    messageId: raw.message_id,
    companyName: raw.company_name,
    recipientRoleTitle: raw.recipient_role_title,
    subject: raw.subject,
    body: raw.body,
    status: raw.status,
    createdAt: raw.created_at,
    sentAt: raw.sent_at,
  };
}
