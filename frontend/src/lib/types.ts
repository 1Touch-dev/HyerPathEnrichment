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
  scoreBreakdown: Record<string, number>;
  explanation: string | null;
  isNew: boolean;
  viewedAt: string | null;
  feedback: "up" | "down" | null;
  createdAt: string;
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

export type BackendModerateJobPostingRequest = {
  moderation_status: ModerationStatus;
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

export type DocumentJobStatus = {
  jobId: string;
  status: string;
  progress: number;
  documentId: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
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
}

export interface SwipeDeck {
  cards: SwipeCard[];
  /** Whether more unswiped matches exist beyond this page (backend's `SwipeDeckResponse.has_more`). */
  hasMore: boolean;
}

export type SwipeDirection = "left" | "right" | "up";

export interface OutreachMessage {
  messageId: string;
  companyName: string;
  recipientRoleTitle: string | null;
  subject: string;
  body: string;
  status: "draft" | "sent";
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
