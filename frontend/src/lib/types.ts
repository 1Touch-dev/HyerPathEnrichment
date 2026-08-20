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
}

/** Mirrors the backend's `JobStatusResponse` (backend/app/modules/documents/schemas.py). */
export interface DocumentJobStatus {
  jobId: string;
  status: string;
  progress: number;
  documentId: string | null;
  error: string | null;
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
 * `documentId` is required by the backend's `OutreachDraftRequest`, but
 * `useDraftOutreachForMatch` resolves it internally before calling `draftOutreach`,
 * so callers of that hook only supply `Omit<RequestOutreachDraftInput, "documentId">`.
 * `customInstruction` is only meaningful (and required, per §11.6's service-layer
 * guard) when `messageType === "custom"`.
 */
export interface RequestOutreachDraftInput {
  companyName: string;
  documentId: string;
  recipientRoleTitle?: string;
  jobMatchId?: string;
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
  jobMatchId: string;
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
