export type RequestedTier = "tier1" | "tier2" | "tier3" | "tier4";

export type JobStatus = "queued" | "running" | "completed" | "failed" | "suppressed";

export type EnrichMode = "async" | "sync";

export type EnrichmentInput = {
  email?: string;
  linkedinUrl?: string;
  username?: string;
  company?: string;
  business?: string;
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
    name: string;
    address: string;
    website: string;
    rating: number;
    phone: string;
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
