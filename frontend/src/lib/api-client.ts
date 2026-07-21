import {
  ApiError,
  isErrorEnvelope,
  isSuccessEnvelope,
  parseEnvelopeError,
  SuccessEnvelope,
} from "@/src/lib/api-envelope";
import {
  DsarInput,
  DsarResponse,
  EnrichmentInput,
  EnrichmentJob,
  EnrichMode,
  HealthStatus,
  JobListResponse,
  OptOutInput,
  SignalListResponse,
} from "@/src/lib/types";

async function parseJsonBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<SuccessEnvelope<T>> {
  const response = await fetch(path, init);
  const body = await parseJsonBody(response);

  if (!response.ok || isErrorEnvelope(body)) {
    throw parseEnvelopeError(body, response.status);
  }

  if (!isSuccessEnvelope(body)) {
    throw new ApiError("Invalid API response shape", {
      code: "INTERNAL_ERROR",
      statusCode: response.status || 500,
    });
  }

  return body as SuccessEnvelope<T>;
}

export async function requestData<T>(path: string, init?: RequestInit): Promise<T> {
  const envelope = await request<T>(path, init);
  return envelope.data;
}

export async function createEnrichmentJob(
  input: EnrichmentInput,
  mode: EnrichMode,
): Promise<SuccessEnvelope<EnrichmentJob>> {
  const path = mode === "sync" ? "/api/enrich/sync" : "/api/enrich";
  return request<EnrichmentJob>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function getEnrichmentJob(id: string): Promise<SuccessEnvelope<EnrichmentJob>> {
  return request<EnrichmentJob>(`/api/enrich/${id}`);
}

export async function listEnrichmentJobs(
  params: { limit?: number; offset?: number } = {},
): Promise<SuccessEnvelope<JobListResponse>> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));

  const query = search.toString();
  return request<JobListResponse>(`/api/enrich/jobs${query ? `?${query}` : ""}`);
}

export async function submitOptOut(
  payload: OptOutInput,
): Promise<SuccessEnvelope<{ status: "accepted" }>> {
  return request<{ status: "accepted" }>("/api/opt-out", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function submitDsar(payload: DsarInput): Promise<SuccessEnvelope<DsarResponse>> {
  return request<DsarResponse>("/api/dsar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listSignals(
  params: { limit?: number; offset?: number } = {},
): Promise<SuccessEnvelope<SignalListResponse>> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));

  const query = search.toString();
  return request<SignalListResponse>(`/api/signals${query ? `?${query}` : ""}`);
}

export async function getHealth(): Promise<SuccessEnvelope<HealthStatus>> {
  return request<HealthStatus>("/api/health");
}
