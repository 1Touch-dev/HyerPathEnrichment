import { Dossier, EnrichmentInput, EnrichmentJob, RequestedTier } from '@/src/lib/types';

type BackendPhoto = {
  source: string;
  asset_url: string;
  captured_at: string;
  confidence: number;
};

type BackendSocialHandle = {
  platform: string;
  username: string;
  profile_url: string;
  confidence: number;
  metadata?: Record<string, string | number | boolean>;
};

type BackendVerifiedEmail = {
  value: string;
  status: string;
  confidence: number;
  source: string;
};

type BackendDossier = {
  photo?: BackendPhoto | null;
  handles?: BackendSocialHandle[];
  emails?: string[];
  verified_emails?: BackendVerifiedEmail[];
  github?: Dossier['github'];
  coworkers?: string[];
  jobs?: Dossier['jobs'];
  business?: Dossier['business'];
  confidence?: Dossier['confidence'];
  sources?: string[];
  metadata?: Record<string, unknown>;
};

export type BackendJobResponse = {
  id: string;
  status: string;
  dossier: BackendDossier;
};

function readMetadataString(metadata: Record<string, unknown>, snakeKey: string, camelKey: string): string {
  const value = metadata[snakeKey] ?? metadata[camelKey];
  return typeof value === 'string' ? value : '';
}

function readMetadataTiers(metadata: Record<string, unknown>): RequestedTier[] {
  const value = metadata.requested_tiers ?? metadata.requestedTiers;
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((tier): tier is RequestedTier =>
    tier === 'tier1' || tier === 'tier2' || tier === 'tier3' || tier === 'tier4',
  );
}

function mapGithub(github: BackendDossier['github']): Dossier['github'] | undefined {
  if (!github || typeof github !== 'object') {
    return undefined;
  }

  const raw = github as Record<string, unknown>;
  const organizations = raw.organizations;
  const publicCommits = raw.public_commits ?? raw.publicCommits;

  return {
    profile: typeof raw.profile === 'string' ? raw.profile : undefined,
    organizations: Array.isArray(organizations)
      ? organizations.filter((org): org is string => typeof org === 'string')
      : [],
    publicCommits: typeof publicCommits === 'number' ? publicCommits : 0,
  };
}

function mapDossier(dossier: BackendDossier): Dossier {
  const metadata = dossier.metadata ?? {};

  return {
    photo: dossier.photo
      ? {
          source: dossier.photo.source,
          assetUrl: dossier.photo.asset_url,
          capturedAt: dossier.photo.captured_at,
          confidence: dossier.photo.confidence,
        }
      : undefined,
    handles: (dossier.handles ?? []).map((handle) => ({
      platform: handle.platform,
      username: handle.username,
      profileUrl: handle.profile_url,
      confidence: handle.confidence,
      metadata: handle.metadata,
    })),
    emails: dossier.emails ?? [],
    verifiedEmails: (dossier.verified_emails ?? []).map((email) => ({
      value: email.value,
      status: email.status as 'verified' | 'risky' | 'unknown',
      confidence: email.confidence,
      source: email.source,
    })),
    github: mapGithub(dossier.github),
    coworkers: dossier.coworkers ?? [],
    jobs: dossier.jobs ?? [],
    business: dossier.business,
    confidence: dossier.confidence ?? [],
    sources: dossier.sources ?? [],
    metadata: {
      generatedAt: readMetadataString(metadata, 'generated_at', 'generatedAt'),
      pipelineId: readMetadataString(metadata, 'pipeline_id', 'pipelineId'),
      requestedTiers: readMetadataTiers(metadata),
      identifierSummary: readMetadataString(metadata, 'identifier_summary', 'identifierSummary'),
    },
  };
}

export function mapBackendJobToFrontend(backendJob: BackendJobResponse, input: EnrichmentInput): EnrichmentJob {
  const status = backendJob.status;
  const normalizedStatus: EnrichmentJob['status'] =
    status === 'queued' || status === 'running' || status === 'completed' ? status : 'completed';

  return {
    id: backendJob.id,
    status: normalizedStatus,
    input,
    dossier: mapDossier(backendJob.dossier),
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
