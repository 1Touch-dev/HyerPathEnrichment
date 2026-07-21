import "server-only";

import { NextResponse } from "next/server";
import {
  errorEnvelope,
  isSuccessEnvelope,
  parseResponseEnvelopeError,
  successEnvelope,
  unwrapEnvelopeData,
} from "@/src/lib/api-envelope";

export function bffSuccess<T>(
  data: T,
  status = 200,
  message: string | null = null,
  meta: Record<string, unknown> | null = null,
) {
  return NextResponse.json(successEnvelope(data, message, meta), { status });
}

export function bffValidationError(message: string, details: unknown = null, status = 400) {
  return NextResponse.json(errorEnvelope("VALIDATION_ERROR", message, status, details), { status });
}

export function bffError(
  code: string,
  message: string,
  status: number,
  details: unknown = null,
  meta: Record<string, unknown> | null = null,
) {
  return NextResponse.json(errorEnvelope(code, message, status, details, meta), { status });
}

export function bffServiceUnavailable(
  message = "Unable to reach enrichment backend.",
  status = 502,
) {
  return NextResponse.json(errorEnvelope("SERVICE_UNAVAILABLE", message, status), { status });
}

export async function backendFailureResponse(response: Response) {
  const apiError = await parseResponseEnvelopeError(response);
  return NextResponse.json(
    errorEnvelope(
      apiError.code,
      apiError.message,
      apiError.statusCode,
      apiError.details ?? null,
      apiError.meta ?? null,
    ),
    { status: apiError.statusCode },
  );
}

type EnvelopeMeta = {
  message?: string | null;
  meta?: Record<string, unknown> | null;
};

export async function handleBackendJson<TBackend, TFrontend>(
  response: Response,
  mapFn: (payload: TBackend) => TFrontend,
  successStatus = 200,
): Promise<NextResponse> {
  if (!response.ok) {
    return backendFailureResponse(response);
  }

  const raw = await response.json();
  const backendData = unwrapEnvelopeData<TBackend>(raw);
  const envelopeMeta: EnvelopeMeta = isSuccessEnvelope(raw)
    ? { message: raw.message ?? null, meta: raw.meta ?? null }
    : { message: null, meta: null };

  return bffSuccess(
    mapFn(backendData),
    successStatus,
    envelopeMeta.message ?? null,
    envelopeMeta.meta ?? null,
  );
}
