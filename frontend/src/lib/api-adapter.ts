import {
  ApplicationStatus,
  AudioRecordingStatus,
  AudioUploadResult,
  CandidateJobPreferences,
  CvChatSession,
  CvCompleteness,
  CvFeedbackReport,
  Dossier,
  DocumentJobStatus,
  DocumentSummary,
  EnrichmentInput,
  EnrichmentJob,
  HealthStatus,
  InterviewQuestion,
  JdPracticeQuestion,
  JdPracticeResponse,
  JobListItem,
  JobListResponse,
  JobMatch,
  JobMatchListResponse,
  JobStatus,
  OptOutInput,
  OutreachMessage,
  PortfolioItem,
  PortfolioProfile,
  PracticeAttempt,
  PracticeSession,
  PracticeSessionListResult,
  PublicPortfolioProfile,
  QuestionListResult,
  RequestedTier,
  DsarInput,
  DsarResponse,
  SignalListItem,
  SignalListResponse,
  SwipeDeck,
  TrackedMatch,
  TrackedMatchListResponse,
} from "@/src/lib/types";
import type {
  BackendAudioStatusResponse,
  BackendAudioUploadResponse,
  BackendDossier,
  BackendDsarResponse,
  BackendHealthResponse,
  BackendJobListItem,
  BackendJobListResponse,
  BackendJobMatchListResponse,
  BackendJobMatchResponse,
  BackendJobPreferencesResponse,
  BackendJobResponse,
  BackendQuestionAttemptResponse,
  BackendQuestionItem,
  BackendQuestionListResponse,
  BackendSessionListResponse,
  BackendSessionResponse,
  BackendSignalListItem,
  BackendSignalListResponse,
} from "@/src/lib/generated/api-schemas";

export type {
  BackendAudioStatusResponse,
  BackendAudioUploadResponse,
  BackendDsarResponse,
  BackendHealthResponse,
  BackendJobListResponse,
  BackendJobMatchListResponse,
  BackendJobMatchResponse,
  BackendJobPreferencesResponse,
  BackendJobResponse,
  BackendQuestionAttemptResponse,
  BackendQuestionListResponse,
  BackendSessionListResponse,
  BackendSessionResponse,
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
    applyClickedAt: item.apply_clicked_at ?? null,
    appliedAt: item.applied_at ?? null,
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

/**
 * Mirrors the backend's real `TrackedMatchResponse`
 * (backend/app/modules/application_tracker/schemas.py, Module 4 §7.4) — hand-declared
 * per this file's own convention (see the `Raw*Response` section below) since that
 * module's routes are being implemented concurrently and have no generated schema yet.
 * Must be deleted and replaced with real `npm run openapi:gen` output once the backend
 * route exists.
 */
export interface BackendTrackedMatchResponse {
  match_id: string;
  job_posting_id: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  source_url: string | null;
  overall_score: number | null;
  application_status: ApplicationStatus;
  apply_clicked_at: string | null;
  applied_at: string | null;
  status_updated_at: string | null;
  created_at: string;
  next_interview_at: string | null;
}

export interface BackendTrackedMatchListResponse {
  matches: BackendTrackedMatchResponse[];
  total: number;
  limit: number;
  offset: number;
  counts_by_status: Record<ApplicationStatus, number>;
}

export function mapBackendTrackedMatchItem(item: BackendTrackedMatchResponse): TrackedMatch {
  return {
    matchId: item.match_id,
    jobPostingId: item.job_posting_id,
    title: item.title,
    company: item.company,
    location: item.location,
    remote: item.remote,
    sourceUrl: item.source_url,
    overallScore: item.overall_score,
    applicationStatus: item.application_status,
    applyClickedAt: item.apply_clicked_at,
    appliedAt: item.applied_at,
    statusUpdatedAt: item.status_updated_at,
    createdAt: item.created_at,
    nextInterviewAt: item.next_interview_at,
  };
}

export function mapBackendTrackedMatchListToFrontend(
  response: BackendTrackedMatchListResponse,
): TrackedMatchListResponse {
  return {
    matches: response.matches.map(mapBackendTrackedMatchItem),
    total: response.total,
    limit: response.limit,
    offset: response.offset,
    countsByStatus: response.counts_by_status,
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
  below_similarity_threshold: boolean;
  source_url: string | null;
  applied_at: string | null;
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
    error: raw.error,
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
      belowSimilarityThreshold: c.below_similarity_threshold,
      sourceUrl: c.source_url,
      appliedAt: c.applied_at,
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

export function mapBackendQuestionItem(raw: BackendQuestionItem): InterviewQuestion {
  return {
    id: raw.id,
    questionText: raw.question_text,
    category: raw.category,
    difficulty: raw.difficulty,
    jobRoles: raw.job_roles,
    technologies: raw.technologies,
    isPersonalized: raw.is_personalized,
  };
}

export function mapBackendQuestionListResponse(
  raw: BackendQuestionListResponse,
): QuestionListResult {
  return {
    questions: raw.questions.map(mapBackendQuestionItem),
    source: raw.source,
  };
}

export function mapBackendQuestionAttempt(raw: BackendQuestionAttemptResponse): PracticeAttempt {
  return {
    id: raw.id,
    sessionId: raw.session_id,
    userId: raw.user_id,
    questionId: raw.question_id,
    // `question_text` is only populated by session_manager.py's read paths
    // (get/list session, add_attempt) — see its docstring; `?? null` covers
    // schema optionality and pre-existing attempts whose question was deleted.
    questionText: raw.question_text ?? null,
    // Backend's response_type is an unconstrained str; narrowed here since the
    // DB CheckConstraint (check_response_type) guarantees only these two values exist.
    responseType: raw.response_type as PracticeAttempt["responseType"],
    textResponse: raw.text_response,
    audioRecordingId: raw.audio_recording_id,
    aiScore: raw.ai_score,
    scoreBreakdown: raw.score_breakdown,
    aiFeedback: raw.ai_feedback,
    timeTakenSeconds: raw.time_taken_seconds,
    attemptedAt: raw.attempted_at,
  };
}

export function mapBackendPracticeSession(raw: BackendSessionResponse): PracticeSession {
  return {
    id: raw.id,
    sessionType: raw.session_type,
    // Backend's status is an unconstrained str; narrowed since the DB
    // CheckConstraint (check_session_status) guarantees only these values exist.
    status: raw.status as PracticeSession["status"],
    questionsAttempted: raw.questions_attempted,
    questionsCompleted: raw.questions_completed,
    overallScore: raw.overall_score,
    startedAt: raw.started_at,
    completedAt: raw.completed_at,
    attempts: (raw.attempts ?? []).map(mapBackendQuestionAttempt),
  };
}

export function mapBackendPracticeSessionList(
  raw: BackendSessionListResponse,
): PracticeSessionListResult {
  return {
    sessions: raw.sessions.map(mapBackendPracticeSession),
    total: raw.total,
    limit: raw.limit,
    offset: raw.offset,
  };
}

export function mapBackendAudioUploadResponse(raw: BackendAudioUploadResponse): AudioUploadResult {
  return {
    id: raw.id,
    practiceSessionId: raw.practice_session_id,
    fileSizeBytes: raw.file_size_bytes,
    transcriptionStatus: raw.transcription_status,
    createdAt: raw.created_at,
  };
}

export function mapBackendAudioStatusResponse(
  raw: BackendAudioStatusResponse,
): AudioRecordingStatus {
  return {
    id: raw.id,
    transcriptionStatus: raw.transcription_status as AudioRecordingStatus["transcriptionStatus"],
    transcription: raw.transcription,
    analysisData: raw.analysis_data as AudioRecordingStatus["analysisData"],
    voiceToneSignals: raw.voice_tone_signals,
    durationSeconds: raw.duration_seconds,
  };
}

// Module 4E: JD-aware interview practice (phase2_module4 §9.4/§9.6)
//
// Mirrors the backend's real `JdPracticeResponse`/`JdPracticeQuestionItem`
// (backend/app/modules/jd_practice/schemas.py) — hand-declared per this file's own
// convention (see the `Raw*Response` section above) since that module is being
// implemented concurrently and has no generated schema yet. Must be deleted and
// replaced with real `npm run openapi:gen` output once the backend route exists.

export interface BackendJdPracticeQuestionItem {
  id: string;
  question_text: string;
  category: JdPracticeQuestion["category"];
  difficulty: JdPracticeQuestion["difficulty"];
  sample_answer: string;
}

export interface BackendJdPracticeResponse {
  questions: BackendJdPracticeQuestionItem[];
  job_match_id: string;
  practice_session_id: string;
}

export function mapBackendJdPracticeQuestionItem(
  raw: BackendJdPracticeQuestionItem,
): JdPracticeQuestion {
  return {
    id: raw.id,
    questionText: raw.question_text,
    category: raw.category,
    difficulty: raw.difficulty,
    sampleAnswer: raw.sample_answer,
  };
}

export function mapBackendJdPracticeResponse(raw: BackendJdPracticeResponse): JdPracticeResponse {
  return {
    questions: raw.questions.map(mapBackendJdPracticeQuestionItem),
    jobMatchId: raw.job_match_id,
    practiceSessionId: raw.practice_session_id,
  };
}
