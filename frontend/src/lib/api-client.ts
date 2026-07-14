import { EnrichmentInput, EnrichmentJob, EnrichMode, HealthStatus, JobListResponse, OptOutInput, DsarInput, DsarResponse } from '@/src/lib/types';

async function parseJson<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T;
  return payload;
}

async function throwApiError(response: Response): Promise<never> {
  let message = 'Request failed';
  try {
    const body = (await response.json()) as { message?: string };
    message = body.message ?? message;
  } catch {
    message = await response.text();
  }
  throw new Error(message || `Request failed (${response.status})`);
}

export async function createEnrichmentJob(input: EnrichmentInput, mode: EnrichMode): Promise<EnrichmentJob> {
  const path = mode === 'sync' ? '/api/enrich/sync' : '/api/enrich';
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    await throwApiError(response);
  }

  return parseJson<EnrichmentJob>(response);
}

export async function getEnrichmentJob(id: string): Promise<EnrichmentJob> {
  const response = await fetch(`/api/enrich/${id}`);

  if (!response.ok) {
    await throwApiError(response);
  }

  return parseJson<EnrichmentJob>(response);
}

export async function listEnrichmentJobs(params: { limit?: number; offset?: number } = {}): Promise<JobListResponse> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));

  const query = search.toString();
  const response = await fetch(`/api/enrich/jobs${query ? `?${query}` : ''}`);

  if (!response.ok) {
    await throwApiError(response);
  }

  return parseJson<JobListResponse>(response);
}

export async function submitOptOut(payload: OptOutInput): Promise<void> {
  const response = await fetch('/api/opt-out', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    await throwApiError(response);
  }
}

export async function submitDsar(payload: DsarInput): Promise<DsarResponse> {
  const response = await fetch('/api/dsar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    await throwApiError(response);
  }

  return parseJson<DsarResponse>(response);
}

export async function getHealth(): Promise<HealthStatus> {
  const response = await fetch('/api/health');

  if (!response.ok) {
    await throwApiError(response);
  }

  return parseJson<HealthStatus>(response);
}
