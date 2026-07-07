export type RequestedTier = 'tier1' | 'tier2' | 'tier3' | 'tier4';

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
  status: 'verified' | 'risky' | 'unknown';
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
  status: 'queued' | 'running' | 'completed';
  input: EnrichmentInput;
  dossier: Dossier;
};
