export type RequestedTier = "tier1" | "tier2" | "tier3" | "tier4";

export type JobStatus =
  "queued" | "running" | "completed" | "completed_no_data" | "failed" | "suppressed";

export type EnrichMode = "async" | "sync";

export type EnrichmentInput = {
  email?: string;
  linkedinUrl?: string;
  username?: string;
  company?: string;
  business?: string;
  jobTitle?: string;
  jobLocation?: string;
  jobCountry?: string;
  jobSearch?: string;
  requestedTiers: RequestedTier[];
};

export type ConfidenceBreakdown = {
  label: string;
  score: number;
  evidence: string[];
};

export type SocialHandle = {
  platform: string;
  username: string;
  profileUrl: string;
  confidence: number;
  metadata?: Record<string, string | number | boolean>;
};

export type VerifiedEmail = {
  value: string;
  status: "verified" | "risky" | "unknown" | "disposable";
  confidence: number;
  source: string;
};

export type Dossier = {
  photo?: {
    source: string;
    assetUrl: string;
    capturedAt: string;
    confidence: number;
  };
  handles: SocialHandle[];
  emails: string[];
  verifiedEmails: VerifiedEmail[];
  github?: {
    profile?: string;
    organizations: string[];
    publicCommits: number;
  };
  coworkers: string[];
  jobs: Array<{
    title: string;
    company: string;
    location: string;
    remote: boolean;
    source: string;
  }>;
  business?: {
    // Core fields
    name: string;
    address: string;
    website: string;
    rating: number;
    phone: string;

    // Location & identification
    category?: string;
    latitude?: number;
    longitude?: number;
    placeId?: string;
    cid?: string;
    plusCode?: string;
    completeAddress?: string;

    // Operations
    openHours?: string;
    popularTimes?: string;
    timezone?: string;
    status?: string;

    // Reviews & ratings
    reviewCount?: number;
    reviewsPerRating?: Record<string, number>;
    reviewsLink?: string;
    userReviews?: Array<{
      text?: string;
      rating?: number;
      timestamp?: string;
    }>;

    // Media
    thumbnail?: string;
    images?: string[];
    streetViewUrl?: string;

    // Commerce
    priceRange?: string;
    reservations?: string;
    orderOnline?: string;
    menu?: string;
    creditCardsAccepted?: string;

    // Additional info
    description?: string;
    about?: string;
    owner?: string;
    emails?: string[];

    // Google Maps references
    link?: string;
    dataId?: string;

    metadata?: Record<string, unknown>;
  };
  confidence: ConfidenceBreakdown[];
  sources: string[];
  metadata: {
    generatedAt: string;
    pipelineId: string;
    requestedTiers: RequestedTier[];
    identifierSummary: string;
  };
};

export type EnrichmentJob = {
  id: string;
  status: JobStatus;
  createdAt: string;
  updatedAt: string;
  input: EnrichmentInput;
  dossier: Dossier;
  error?: string;
  progressMetadata?: {
    currentTier?: RequestedTier;
    completedTiers?: RequestedTier[];
    pendingTiers?: RequestedTier[];
    estimatedSecondsRemaining?: number;
    tierTiming?: Record<
      string,
      {
        startedAt?: string;
        completedAt?: string;
      }
    >;
  };
};

export type JobListItem = {
  id: string;
  status: JobStatus;
  createdAt: string;
  updatedAt: string;
  identifierSummary: string;
  requestedTiers: RequestedTier[];
};

export type JobListResponse = {
  jobs: JobListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type OptOutInput = {
  identifier: string;
  reason?: string;
};

export type DsarType = "access" | "deletion";

export type DsarInput = {
  identifier: string;
  requestType: DsarType;
  notes?: string;
};

export type DsarResponse = {
  id: string;
  status: string;
  requestType: DsarType;
  createdAt: string;
  completedAt?: string | null;
  summary: Record<string, unknown>;
};

export type HealthStatus = {
  status: string;
  service: string;
};

export type SignalListItem = {
  id: string;
  source: string;
  watchId: string;
  title: string;
  url: string;
  timestamp?: string | null;
  createdAt: string;
};

export type SignalListResponse = {
  signals: SignalListItem[];
  total: number;
  limit: number;
  offset: number;
};

// Type aliases for easier component imports
export type PhotoAsset = NonNullable<Dossier["photo"]>;
export type JobListing = Dossier["jobs"][number];
export type BusinessProfile = NonNullable<Dossier["business"]>;

// Module 1: AI Job Matching & Notifications
// NOTE: distinct from JobListing (Dossier tier-4 enrichment output) and
// JobListResponse (enrichment task records) — see phase2_module1.md §4.

export type CandidateJobPreferences = {
  userId: string;
  sourceDocumentId: string | null;
  desiredRoles: string[];
  desiredLocations: string[];
  remotePreference: "remote" | "hybrid" | "onsite" | null;
  salaryMin: number | null;
  salaryMax: number | null;
  salaryCurrency: string;
  notificationChannels: ("email" | "sms" | "webhook" | "push")[];
  webhookUrl: string | null;
  digestFrequency: "daily" | "weekly" | "off";
  isScanEnabled: boolean;
  lastScannedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type JobMatch = {
  matchId: string;
  jobPostingId: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  source: string;
  sourceUrl: string | null;
  salaryMin: number | null;
  salaryMax: number | null;
  salaryCurrency: string | null;
  overallScore: number;
  scoreBreakdown: Record<string, number | boolean>;
  explanation: string | null;
  isBlurred?: boolean;
  isNew: boolean;
  viewedAt: string | null;
  feedback: "up" | "down" | null;
  createdAt: string;
  applyClickedAt: string | null;
  appliedAt: string | null;
};

export type JobMatchListResponse = {
  matches: JobMatch[];
  total: number;
  limit: number;
  offset: number;
};

// Real-time piece (not in phase2_module1.md §10/§11 — added on top of the spec to
// support the `/api/job-matching/events` SSE route; see useUnreadMatchEvents).
export type UnreadMatchCountEvent = {
  unreadCount: number;
};

// Admin module: user/role management, audit logs, feature flags, queue
// introspection, system health, analytics, MFA, and impersonation
// (mirrors backend/app/modules/admin/schemas.py, camelCase).

export type AdminRole = {
  id: string;
  name: string;
  description: string | null;
  isSystem: boolean;
};

export type AdminPermission = {
  id: string;
  resource: string;
  action: string;
  description: string | null;
};

export type AdminRoleWithPermissions = AdminRole & {
  permissions: AdminPermission[];
};

export type AdminUser = {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  isActive: boolean;
  isVerified: boolean;
  isSuperuser: boolean;
  roleId: string | null;
  roleName: string | null;
  mfaEnabled: boolean;
  createdAt: string;
  deletedAt: string | null;
};

export type AdminUserListResponse = {
  items: AdminUser[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type AdminAuditLogEntry = {
  id: string;
  actorUserId: string | null;
  impersonatedBy: string | null;
  action: string;
  targetType: string;
  targetId: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ipAddress: string | null;
  capturedBy: "explicit" | "fallback";
  createdAt: string;
};

export type AdminAuditLogListResponse = {
  items: AdminAuditLogEntry[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type AiAction = {
  id: string;
  actionType: string;
  candidateUserId: string | null;
  triggeredByUserId: string | null;
  relatedId: string | null;
  summary: string | null;
  createdAt: string;
};

export type AiActionListResponse = {
  items: AiAction[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type FeatureFlag = {
  key: string;
  enabled: boolean;
  value: Record<string, unknown> | null;
  description: string | null;
  updatedBy: string | null;
  updatedAt: string;
};

export type QueueSnapshot = {
  name: string;
  priority: number;
  queuedCount: number;
  failedCount: number;
  oldestQueuedAgeSeconds: number | null;
  workersListening: number;
};

export type FailedJob = {
  jobId: string;
  queueName: string;
  funcName: string | null;
  enqueuedAt: string | null;
  failedAt: string | null;
  excInfo: string | null;
};

export type SystemHealthSnapshot = {
  service?: string;
  databaseOk: boolean;
  databaseLatencyMs: number;
  redisOk: boolean;
  redisLatencyMs: number;
  prometheusConfigured: boolean;
  signals: Record<string, number | null>;
};

export type JobMatchAnalytics = {
  totalPostings: number;
  totalMatches: number;
  postingsBySource: Record<string, number>;
  topCompanies: { company: string; count: number }[];
  avgSalaryMin: number | null;
  avgSalaryMax: number | null;
  avgOverallScore: number | null;
  computedAt: string;
  cacheHit: boolean;
};

export type MfaStatus = {
  mfaEnabled: boolean;
  mfaEnrolledAt: string | null;
};

export type MfaEnrollResult = {
  secret: string;
  provisioningUri: string;
};

export type ImpersonationStatus = {
  isImpersonating: boolean;
  adminUserId: string | null;
  adminEmail: string | null;
  targetUserId: string | null;
  expiresAt: string | null;
};

// Generic moderation review queue (backend/app/modules/admin/review_queue_router.py).
// This router is not yet exported to openapi.json/src/lib/generated (Batch 4's
// centralized wiring), so — following this file's own "hand-declare, mirror the
// backend snake_case shape, replace with real openapi:gen output later" convention
// (see the Module 2 `Raw*Response` types in api-adapter.ts for the established
// precedent) — the Backend* shapes live here as plain hand-written types instead.

export type AdminReviewQueueResourceType =
  | "job_posting"
  | "document"
  | "portfolio_item"
  | "outreach_message"
  | "question"
  | "practice_audio";

export type AdminReviewQueueStatus = "pending" | "approved" | "rejected";

export type AdminReviewQueueFlagSource = "heuristic" | "llm_judge" | "user_report";

export type BackendAdminReviewQueueItem = {
  id: string;
  resource_type: AdminReviewQueueResourceType;
  resource_id: string;
  status: AdminReviewQueueStatus;
  flag_reason: string | null;
  flag_source: AdminReviewQueueFlagSource;
  flagged_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
};

export type BackendAdminReviewQueueListResponse = {
  items: BackendAdminReviewQueueItem[];
  next_cursor: string | null;
  has_more: boolean;
};

export type BackendAdminReviewQueueDetail = {
  item: BackendAdminReviewQueueItem;
  resolved_resource: Record<string, unknown> | null;
};

export type BackendAdminReviewQueueDecideRequest = {
  status: "approved" | "rejected";
  review_notes?: string | null;
};

export type AdminReviewQueueItem = {
  id: string;
  resourceType: AdminReviewQueueResourceType;
  resourceId: string;
  status: AdminReviewQueueStatus;
  flagReason: string | null;
  flagSource: AdminReviewQueueFlagSource;
  flaggedAt: string;
  reviewedBy: string | null;
  reviewedAt: string | null;
  reviewNotes: string | null;
};

export type AdminReviewQueueListResponse = {
  items: AdminReviewQueueItem[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type AdminReviewQueueDetail = {
  item: AdminReviewQueueItem;
  /** Best-effort snapshot of the flagged resource; null for Module-3 placeholders,
   * unrecognized resource types, or a resource that no longer exists. */
  resolvedResource: Record<string, unknown> | null;
};

// Job postings moderation (Admin Module Phase 2 — moderation layer,
// mirrors backend/app/modules/admin/job_postings_router.py, camelCase).

export type ModerationStatus = "active" | "hidden" | "removed";

export type AdminJobPosting = {
  id: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  source: string;
  sourceUrl: string | null;
  salaryMin: number | null;
  salaryMax: number | null;
  salaryCurrency: string | null;
  postedAt: string | null;
  firstSeenAt: string;
  lastSeenAt: string;
  isActive: boolean;
  moderationStatus: ModerationStatus;
  moderatedBy: string | null;
  moderatedAt: string | null;
};

export type AdminJobPostingListResponse = {
  items: AdminJobPosting[];
  nextCursor: string | null;
  hasMore: boolean;
};

/**
 * Mirrors backend/app/modules/admin/job_postings_router.py's
 * `AdminJobPostingResponse`/`AdminJobPostingListResponse` Pydantic models.
 * Hand-declared here (snake_case, not generated) because `openapi/openapi.json`
 * and `src/lib/generated/openapi.ts` are held back for centralized regeneration
 * elsewhere in this plan — same rationale as the `Raw*Response` placeholders
 * below for Module 2, but named `Backend*` since this backend route already
 * exists (not speculative). Should be replaced by real generated types once
 * `npm run openapi:gen` is re-run against the merged router.
 */
export type BackendAdminJobPostingResponse = {
  id: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  source: string;
  source_url: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  posted_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  is_active: boolean;
  moderation_status: ModerationStatus;
  moderated_by: string | null;
  moderated_at: string | null;
};

export type BackendAdminJobPostingListResponse = {
  items: BackendAdminJobPostingResponse[];
  next_cursor: string | null;
  has_more: boolean;
};

// Admin documents moderation: soft-delete/restore of candidate documents
// (mirrors backend/app/modules/admin/documents_router.py's inline Pydantic
// models — distinct from the candidate-facing CandidateDocument/CandidateDocumentDetail
// types below, which come from app/modules/documents/schemas.py instead).

export type AdminDocumentModerateAction = "soft_delete" | "restore";

/**
 * Wire shape of `documents_router.py`'s `AdminDocumentResponse` — declared by hand
 * here (not sourced from `src/lib/generated/api-schemas.ts`) because that router's
 * inline Pydantic models are not part of the committed OpenAPI schema yet, matching
 * this file's existing `Raw*Response` convention (see `api-adapter.ts`) for
 * not-yet-generated backend contracts.
 */
export type BackendAdminDocumentResponse = {
  id: string;
  user_id: string;
  document_type: string;
  original_filename: string;
  mime_type: string | null;
  file_size_bytes: number;
  processing_status: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
};

export type BackendAdminDocumentListResponse = {
  items: BackendAdminDocumentResponse[];
  next_cursor: string | null;
  has_more: boolean;
};

// Outreach moderation (mirrors backend/app/modules/admin/outreach_router.py's
// AdminOutreachMessageResponse/AdminOutreachMessageListResponse). That router's schemas
// are not yet in the committed OpenAPI schema (frontend/openapi/openapi.json), so — unlike
// the other admin types above, whose Backend* counterparts live in
// src/lib/generated/api-schemas.ts — the Backend* types below are hand-declared here.
// Delete these and switch to generated types once `npm run openapi:gen` picks up this router.

/** `OutreachMessage.status` is a free-form `String(20)` column on the backend model
 * (backend/app/modules/outreach/models.py), not a fixed enum — currently observed values
 * are "draft" and "sent", but this is intentionally typed as `string` rather than a union. */
export type BackendAdminOutreachMessage = {
  id: string;
  user_id: string;
  job_match_id: string | null;
  recipient_role_title: string | null;
  company_name: string;
  subject: string;
  body: string;
  status: string;
  admin_blocked: boolean;
  sent_at: string | null;
  created_at: string;
};

export type BackendAdminOutreachMessageListResponse = {
  items: BackendAdminOutreachMessage[];
  next_cursor: string | null;
  has_more: boolean;
};

export type BackendModerateJobPostingRequest = {
  moderation_status: ModerationStatus;
  reason?: string | null;
};

export type BackendModerateDocumentRequest = {
  action: AdminDocumentModerateAction;
  reason?: string | null;
};

export type AdminDocument = {
  id: string;
  userId: string;
  documentType: string;
  originalFilename: string;
  mimeType: string | null;
  fileSizeBytes: number;
  processingStatus: string;
  createdAt: string;
  updatedAt: string;
  deletedAt: string | null;
};

export type AdminDocumentListResponse = {
  items: AdminDocument[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type AdminOutreachMessage = {
  id: string;
  userId: string;
  jobMatchId: string | null;
  recipientRoleTitle: string | null;
  companyName: string;
  subject: string;
  body: string;
  status: string;
  adminBlocked: boolean;
  sentAt: string | null;
  createdAt: string;
};

export type AdminOutreachMessageListResponse = {
  items: AdminOutreachMessage[];
  nextCursor: string | null;
  hasMore: boolean;
};

// LinkedIn send task queue + operator-triggered automated-batch mode (machine-2/06,
// mirrors backend/app/modules/outreach/linkedin_send_router.py's
// LinkedInSendTaskResponse/LinkedInTaskListResponse/LinkedInSendBatchResponse). Not
// yet in the committed OpenAPI schema — hand-declared here, same as the outreach
// moderation Backend* types above. Delete and switch to generated types once
// `npm run openapi:gen` picks up this router.

export type BackendLinkedInSendTask = {
  id: string;
  outreach_message_id: string;
  batch_id: string | null;
  linkedin_profile_url: string;
  action_type: "connection_request" | "inmail" | "direct_message";
  status: "pending" | "claimed" | "completed" | "skipped";
  claimed_by: string | null;
  claimed_at: string | null;
  completed_at: string | null;
  outcome_note: string | null;
  created_at: string;
};

export type BackendLinkedInTaskListResponse = {
  tasks: BackendLinkedInSendTask[];
};

export type BackendLinkedInSendBatch = {
  id: string;
  triggered_by: string | null;
  multilogin_profile_id: string;
  status: "pending" | "running" | "completed" | "cancelled" | "failed";
  max_sends_per_day: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
};

export type LinkedInSendTask = {
  id: string;
  outreachMessageId: string;
  batchId: string | null;
  linkedinProfileUrl: string;
  actionType: BackendLinkedInSendTask["action_type"];
  status: BackendLinkedInSendTask["status"];
  claimedBy: string | null;
  claimedAt: string | null;
  completedAt: string | null;
  outcomeNote: string | null;
  createdAt: string;
};

export type LinkedInSendBatch = {
  id: string;
  triggeredBy: string | null;
  multiloginProfileId: string;
  status: BackendLinkedInSendBatch["status"];
  maxSendsPerDay: number;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
};

// Admin portfolio moderation (mirrors backend/app/modules/admin/portfolio_router.py,
// camelCase). Distinct from the candidate-facing `PortfolioProfile`/`PortfolioItem`
// below — the admin variants expose moderation fields (`adminHidden`) and are never
// shaped for the public /p/{slug} page.

export type AdminPortfolioItem = {
  itemId: string;
  itemType: string;
  title: string;
  description: string | null;
  url: string;
  imageUrl: string | null;
  displayOrder: number;
  createdAt: string;
};

export type AdminPortfolioProfile = {
  profileId: string;
  userId: string;
  slug: string;
  displayName: string | null;
  headline: string | null;
  bio: string | null;
  isPublished: boolean;
  adminHidden: boolean;
  createdAt: string;
  updatedAt: string;
};

export type AdminPortfolioProfileDetail = AdminPortfolioProfile & {
  items: AdminPortfolioItem[];
};

export type AdminPortfolioProfileListResponse = {
  items: AdminPortfolioProfile[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type AdminDocumentFilters = {
  processingStatus: string | null;
  deleted: boolean | null;
};

// Backend (snake_case) counterparts for the admin portfolio moderation types above.
// backend/app/modules/admin/portfolio_router.py defines these models inline (no
// dedicated schemas.py for the admin portfolio module), and this router isn't in
// the committed OpenAPI schema yet, so — following this file's own convention for
// not-yet-generated backend routes (see the `Raw*Response` types further below) —
// these are hand-declared here rather than imported from `generated/api-schemas.ts`.

export type BackendAdminPortfolioItem = {
  item_id: string;
  item_type: string;
  title: string;
  description: string | null;
  url: string;
  image_url: string | null;
  display_order: number;
  created_at: string;
};

export type BackendAdminPortfolioProfile = {
  profile_id: string;
  user_id: string;
  slug: string;
  display_name: string | null;
  headline: string | null;
  bio: string | null;
  is_published: boolean;
  admin_hidden: boolean;
  created_at: string;
  updated_at: string;
};

export type BackendAdminPortfolioProfileDetail = BackendAdminPortfolioProfile & {
  items: BackendAdminPortfolioItem[];
};

export type BackendAdminPortfolioProfileListResponse = {
  items: BackendAdminPortfolioProfile[];
  next_cursor: string | null;
  has_more: boolean;
};

export type BackendModeratePortfolioRequest = {
  admin_hidden: boolean;
  reason?: string | null;
};

// Documents module: candidate document upload, processing, and search
// (mirrors backend/app/modules/documents/schemas.py, camelCase).

export type DocumentType = "cv" | "cover_letter";

export type CandidateDocument = {
  documentId: string;
  documentType: DocumentType;
  originalFilename: string;
  fileSizeBytes: number;
  processingStatus: string;
  createdAt: string;
};

export type CandidateDocumentDetail = {
  documentId: string;
  documentType: DocumentType;
  originalFilename: string;
  fileSizeBytes: number;
  processingStatus: string;
  rawText: string | null;
  extractedData: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
};

export type DocumentUploadResult = {
  jobId: string;
  documentId: string;
  message: string;
};

export type CvData = {
  documentId: string;
  extractedData: Record<string, unknown>;
  rawText: string | null;
  processingStatus: string;
  createdAt: string;
  updatedAt: string;
};

export type DocumentSearchResult = {
  documentId: string;
  similarityScore: number;
  cvData: Record<string, unknown>;
  excerpt: string;
};

export type DocumentSearchResponse = {
  results: DocumentSearchResult[];
};

// Module 4, Module C: Job application tracking board (phase2_module4_application_lifecycle_and_interview_prep.md §7.6)

export type ApplicationStatus = "new" | "applied" | "replied" | "interview" | "offer" | "rejected";

export type TrackedMatch = {
  matchId: string;
  jobPostingId: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  sourceUrl: string | null;
  overallScore: number | null; // null for Module F manual entries (§10)
  applicationStatus: ApplicationStatus;
  applyClickedAt: string | null;
  appliedAt: string | null;
  statusUpdatedAt: string | null;
  createdAt: string;
  nextInterviewAt: string | null; // Module D
};

export type TrackedMatchListResponse = {
  matches: TrackedMatch[];
  total: number;
  limit: number;
  offset: number;
  countsByStatus: Record<ApplicationStatus, number>;
};

// Module 4, Module D: Interview scheduling, calendar, and notifications
// (phase2_module4_application_lifecycle_and_interview_prep.md §8.7/§8.8)

export interface InterviewSchedule {
  id: string;
  jobMatchId: string;
  scheduledAt: string;
  durationMinutes: number;
  notes: string | null;
  icsDownloadUrl: string;
  googleCalendarLink: string;
  createdAt: string;
}

// Module 2: Tinder-Style Job Board + CV Management (phase2_module2.md §11.2)

export interface CvCompleteness {
  documentId: string;
  completenessScore: number;
  missingFields: string[];
  hasActiveChatSession: boolean;
}

export interface CvChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  createdAt: string;
}

export interface CvChatSession {
  sessionId: string;
  status: "active" | "completed" | "abandoned";
  missingFieldsAtStart: string[];
  fieldsResolved: string[];
  messages: CvChatMessage[];
}

/**
 * Mirrors the backend's `CvFeedbackResponse` (backend/app/modules/documents/schemas.py) —
 * a `CvFeedbackReport` row is only ever created once generation is fully complete (see
 * `backend/app/workers/tasks/cv_improvement.py`), so there is no "pending" shape of this
 * type. "Is generation still running?" is answered separately, via `DocumentJobStatus`
 * (the real `job_id` returned by `requestCvFeedback`), not by a field on this type.
 */
export interface CvFeedbackReport {
  reportId: string;
  documentId: string;
  targetRole: string | null;
  atsScore: number;
  strengths: string[];
  improvements: string[];
  rewrittenBullets: { original: string; rewritten: string; rationale: string }[];
  /** Indices into `rewrittenBullets` the user has already accepted (backend's `accepted_bullet_indices`). */
  acceptedBulletIndices: number[];
  createdAt: string;
  isBlurred?: boolean;
}

export type SubscriptionStatus = {
  planTier: string;
  status: string;
  currentPeriodEnd: string | null;
  stripeCustomerId: string | null;
  stripeSubscriptionId: string | null;
  effectiveTier: "free" | "premium";
};

export type CheckoutSession = {
  url: string;
};

export type PortalSession = {
  url: string;
};

/** Mirrors the backend's `JobStatusResponse` (backend/app/modules/documents/schemas.py). */
export interface DocumentJobStatus {
  jobId: string;
  status: string;
  progress: number;
  documentId: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
}

/** Mirrors the backend's `DocumentMetadata` (backend/app/modules/documents/schemas.py). */
export interface DocumentSummary {
  documentId: string;
  documentType: string;
  originalFilename: string;
  fileSizeBytes: number;
  processingStatus: string;
  createdAt: string;
}

export interface PortfolioItem {
  itemId: string;
  itemType: "github_repo" | "live_demo" | "case_study" | "other_link";
  title: string;
  description: string | null;
  url: string;
  displayOrder: number;
}

export interface PortfolioProfile {
  profileId: string;
  userId: string;
  slug: string;
  displayName: string | null;
  headline: string | null;
  summary: string | null;
  isPublished: boolean;
  /** Absolute or root-relative URL to the public /p/{slug} page (backend's `PortfolioProfileResponse.public_url`). */
  publicUrl: string;
  items: PortfolioItem[];
  createdAt: string;
  updatedAt: string;
}

export interface PublicPortfolioProfile {
  slug: string;
  displayName: string | null;
  headline: string | null;
  summary: string | null;
  items: PortfolioItem[];
  // Deliberately no profileId/userId/publicUrl/timestamps — public response never leaks
  // internal IDs (§9.6), and the visitor is already on the public URL so it isn't needed.
}

export interface SwipeCard {
  matchId: string;
  jobPostingId: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  salaryMin: number | null;
  salaryMax: number | null;
  salaryCurrency: string | null;
  overallScore: number;
  explanation: string | null;
  isBlurred?: boolean;
  belowSimilarityThreshold: boolean;
  sourceUrl: string | null;
  appliedAt: string | null;
}

export interface SwipeDeck {
  cards: SwipeCard[];
  /** Whether more unswiped matches exist beyond this page (backend's `SwipeDeckResponse.has_more`). */
  hasMore: boolean;
}

export type SwipeDirection = "left" | "right" | "up";

// Module 4, Module G: multi-channel outreach message types
// (phase2_module4_application_lifecycle_and_interview_prep.md §11.4/§11.7).
export type OutreachMessageType = "email" | "linkedin" | "generic" | "custom";

// machine-2/03 (outreach strategy dimension): the drafting *approach* — independent
// of `OutreachMessageType`'s channel dimension above. Mirrors the backend's
// `OutreachStrategy` literal (backend/app/modules/outreach/schemas.py).
export type OutreachStrategy = "direct_pitch" | "value_first" | "curiosity" | "warm_referral";

// machine-2/03: role-type/seniority are recruiter-supplied, optional drafting
// adjustments, independent of `OutreachStrategy`/`OutreachMessageType` above.
// Mirror the backend's `OutreachRoleType`/`OutreachSeniority` literals.
export type OutreachRoleType = "technical" | "non_technical";
export type OutreachSeniority = "junior" | "senior";

// machine-2/03: manual, recruiter-set employer classification (NOT auto-computed —
// see backend's `EmployerCompanyTier`). Persists across every future draft for the
// same `companyName`.
export type OutreachCompanyTierValue = "premium" | "outsourcing";

/** Mirrors the backend's `CompanyTierResponse` (backend/app/modules/outreach/schemas.py). */
export interface OutreachCompanyTier {
  companyName: string;
  tier: OutreachCompanyTierValue;
  notes: string | null;
  updatedAt: string;
}

export interface OutreachMessage {
  messageId: string;
  companyName: string;
  recipientRoleTitle: string | null;
  subject: string;
  body: string;
  status: "draft" | "sent";
  messageType: OutreachMessageType;
  createdAt: string;
  sentAt: string | null;
}

export interface OutreachListResponse {
  messages: OutreachMessage[];
}

/**
 * `POST /api/outreach/drafts` is async — it enqueues an RQ job and returns this
 * immediately; the actual `OutreachMessage` row only exists once the worker finishes
 * and shows up later via `GET /api/outreach` (backend/app/modules/outreach/service.py's
 * `request_draft`). There is no `OutreachMessage` to return synchronously.
 */
export interface OutreachDraftAccepted {
  rqJobId: string;
  message: string;
}

/**
 * Module 4, Module G: request payload for `POST /api/outreach/drafts`
 * (phase2_module4_application_lifecycle_and_interview_prep.md §11.4/§11.7).
 * `documentId` is required (chosen in DraftOutreachDialog's résumé picker).
 * Optional `jobDescription` pastes override match-lookup JD text in the worker.
 * `customInstruction` is only meaningful (and required, per §11.6's service-layer
 * guard) when `messageType === "custom"`.
 */
export interface RequestOutreachDraftInput {
  companyName: string;
  documentId: string;
  recipientRoleTitle?: string;
  jobMatchId?: string;
  jobDescription?: string;
  messageType?: OutreachMessageType;
  customInstruction?: string;
}

export interface InterviewQuestion {
  id: string;
  questionText: string;
  category: "behavioral" | "technical" | "system_design";
  difficulty: "easy" | "medium" | "hard";
  jobRoles: string[];
  technologies: string[];
  isPersonalized: boolean;
}

export interface QuestionListResult {
  questions: InterviewQuestion[];
  source: "question_bank" | "generated" | "mixed";
}

export interface PracticeAttempt {
  id: string;
  sessionId: string;
  userId: string;
  questionId: string | null;
  questionText: string | null;
  responseType: "text" | "audio";
  textResponse: string | null;
  audioRecordingId: string | null;
  aiScore: number | null;
  scoreBreakdown: Record<string, unknown> | null;
  aiFeedback: string | null;
  timeTakenSeconds: number | null;
  attemptedAt: string;
}

export interface PracticeSession {
  id: string;
  sessionType: string;
  status: "pending" | "in_progress" | "completed" | "failed" | "abandoned";
  questionsAttempted: number;
  questionsCompleted: number;
  overallScore: number | null;
  startedAt: string;
  completedAt: string | null;
  attempts: PracticeAttempt[];
}

export interface PracticeSessionListResult {
  sessions: PracticeSession[];
  total: number;
  limit: number;
  offset: number;
}

export interface AudioUploadResult {
  id: string;
  practiceSessionId: string;
  fileSizeBytes: number;
  transcriptionStatus: string;
  createdAt: string;
}

export interface AudioRecordingStatus {
  id: string;
  transcriptionStatus: "pending" | "processing" | "completed" | "failed" | string;
  transcription: string | null;
  analysisData: { fillerWordCount?: number; wordsPerMinute?: number; clarityScore?: number } | null;
  voiceToneSignals: Record<string, unknown> | null;
  durationSeconds: number | null;
}

// Module 4E: JD-aware interview practice (phase2_module4 §9.6)

export interface JdPracticeQuestion {
  id: string;
  questionText: string;
  category: "behavioral" | "technical" | "system_design";
  difficulty: "easy" | "medium" | "hard";
  // Returned by the API for every question up front (backend/app/modules/jd_practice/schemas.py
  // §9.4), but the frontend must not render this until the candidate has submitted an
  // attempt for that question — a UI-layer discipline, not a schema-layer omission.
  sampleAnswer: string;
}

export interface JdPracticeResponse {
  questions: JdPracticeQuestion[];
  jobMatchId: string | null;
  practiceSessionId: string;
}

// Module 4, Module F: manually-added job entries (phase2_module4_application_lifecycle_and_interview_prep.md §10.7)
// Mirrors the backend's real `ManualJobEntryResponse` (backend/app/modules/manual_jobs/schemas.py).
// v1 is create-only — no edit/delete affordance anywhere for this type (§14 non-goal).
export interface ManualJobEntry {
  id: string;
  title: string;
  company: string;
  location: string | null;
  sourceLabel: string | null;
  sourceUrl: string | null;
  notes: string | null;
  /** The auto-created tracker row's id — lets the frontend navigate straight to it. */
  jobMatchId: string;
  createdAt: string;
}

// Brand landing / admin (Wave 2). Public DTO mirrors PublicBrandResponse —
// name, slug, landing_page_tier_config only. AdminBrand mirrors BrandResponse.

export type PublicBrand = {
  name: string;
  slug: string;
  landingPageTierConfig: Record<string, unknown> | null;
};

export type AdminBrand = {
  id: string;
  name: string;
  slug: string;
  customDomain: string | null;
  chatbotConfig: Record<string, unknown> | null;
  landingPageTierConfig: Record<string, unknown> | null;
  isActive: boolean;
  createdAt: string;
};

/** Create payload — required name + slug; write-key allowlist only (no isActive). */
export type AdminBrandCreate = {
  name: string;
  slug: string;
  customDomain?: string | null;
  chatbotConfig?: Record<string, unknown> | null;
  landingPageTierConfig?: Record<string, unknown> | null;
};

/** PATCH allowlist — all five optional. No id / isActive / createdAt. */
export type AdminBrandUpdate = {
  name?: string;
  slug?: string;
  customDomain?: string | null;
  chatbotConfig?: Record<string, unknown> | null;
  landingPageTierConfig?: Record<string, unknown> | null;
};
