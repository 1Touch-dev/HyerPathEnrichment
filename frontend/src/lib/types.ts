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
  notificationChannels: ("email" | "sms" | "webhook")[];
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
