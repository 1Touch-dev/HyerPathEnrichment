import {
  Dossier,
  EnrichmentInput,
  EnrichmentJob,
  HealthStatus,
  JobListItem,
  JobListResponse,
  JobStatus,
  OptOutInput,
  RequestedTier,
  DsarInput,
  DsarResponse,
} from '@/src/lib/types';

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
  error?: string;
};

type BackendJobListItem = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  request_payload?: Record<string, unknown>;
  identifier_summary?: string;
};

type BackendJobListResponse = {
  jobs: BackendJobListItem[];
  total: number;
  limit: number;
  offset: number;
};

type BackendHealthResponse = {
  status: string;
  service?: string;
};

function normalizeJobStatus(status: string): JobStatus {
  if (
    status === 'queued' ||
    status === 'running' ||
    status === 'completed' ||
    status === 'failed' ||
    status === 'suppressed'
  ) {
    return status;
  }
  return 'failed';
}

function readMetadataString(metadata: Record<string, unknown>, snakeKey: string, camelKey: string): string {
  const value = metadata[snakeKey] ?? metadata[camelKey];
  return typeof value === 'string' ? value : '';
}

function readMetadataTiers(metadata: Record<string, unknown>): RequestedTier[] {
  const value = metadata.requested_tiers ?? metadata.requestedTiers;
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (tier): tier is RequestedTier =>
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
          capturedAt:
            typeof dossier.photo.captured_at === 'string'
              ? dossier.photo.captured_at
              : String(dossier.photo.captured_at ?? ''),
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
      status: email.status as 'verified' | 'risky' | 'unknown' | 'disposable',
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

function identifierSummaryFromPayload(payload: Record<string, unknown> | undefined): string {
  if (!payload) {
    return '';
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
  ].filter((v): v is string => typeof v === 'string' && v.length > 0);
  return values.join(' • ');
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
      tier === 'tier1' || tier === 'tier2' || tier === 'tier3' || tier === 'tier4',
  );
}

export function mapBackendJobToFrontend(
  backendJob: BackendJobResponse,
  input: EnrichmentInput,
): EnrichmentJob {
  return {
    id: backendJob.id,
    status: normalizeJobStatus(backendJob.status),
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

type BackendDsarResponse = {
  id: string;
  status: string;
  request_type: string;
  created_at: string;
  completed_at?: string | null;
  summary: Record<string, unknown>;
};

export function mapBackendDsarResponse(response: BackendDsarResponse): DsarResponse {
  return {
    id: response.id,
    status: response.status,
    requestType: response.request_type as DsarInput['requestType'],
    createdAt: response.created_at,
    completedAt: response.completed_at,
    summary: response.summary ?? {},
  };
}

export function mapBackendHealth(response: BackendHealthResponse): HealthStatus {
  return {
    status: response.status,
    service: response.service ?? 'hyrepath-enrichment',
  };
}

export function parseEnrichmentInput(body: Partial<EnrichmentInput>): EnrichmentInput {
  return {
    email: body.email?.trim() || '',
    linkedinUrl: body.linkedinUrl?.trim() || '',
    username: body.username?.trim() || '',
    company: body.company?.trim() || '',
    business: body.business?.trim() || '',
    jobSearch: body.jobSearch?.trim() || '',
    requestedTiers: body.requestedTiers?.length ? body.requestedTiers : ['tier1', 'tier2', 'tier3', 'tier4'],
  };
}

export function hasIdentifier(input: EnrichmentInput): boolean {
  return Boolean(
    input.email || input.linkedinUrl || input.username || input.company || input.business || input.jobSearch,
  );
}

export async function parseBackendError(response: Response): Promise<string> {
  const detail = await response.text();
  let message = detail || 'Backend error';

  try {
    const parsed = JSON.parse(detail) as { detail?: string | Array<{ msg?: string }>; message?: string };
    if (typeof parsed.message === 'string') {
      return parsed.message;
    }
    if (typeof parsed.detail === 'string') {
      return parsed.detail;
    }
    if (Array.isArray(parsed.detail)) {
      return parsed.detail.map((item) => item.msg).filter(Boolean).join(', ') || message;
    }
  } catch {
    // keep raw detail text
  }

  return message;
}
