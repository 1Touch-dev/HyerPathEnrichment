import { NextRequest, NextResponse } from 'next/server';
import {
  BackendJobResponse,
  hasIdentifier,
  mapBackendJobToFrontend,
  parseBackendError,
  parseEnrichmentInput,
  toBackendEnrichmentRequest,
  unwrapBackendData,
} from '@/src/lib/api-adapter';
import { backendFetch } from '@/src/lib/backend-client';

export async function POST(request: NextRequest) {
  const body = (await request.json()) as Parameters<typeof parseEnrichmentInput>[0];
  const input = parseEnrichmentInput(body);

  if (!hasIdentifier(input)) {
    return NextResponse.json({ message: 'At least one identifier is required.' }, { status: 400 });
  }

  if (input.requestedTiers.includes('tier1')) {
    return NextResponse.json(
      { message: 'Tier 1 is not available in sync mode. Use async enrichment or remove tier1.' },
      { status: 400 },
    );
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch('/enrich/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(toBackendEnrichmentRequest(input)),
    });
  } catch {
    return NextResponse.json({ message: 'Unable to reach enrichment backend.' }, { status: 502 });
  }

  if (!backendResponse.ok) {
    const message = await parseBackendError(backendResponse);
    return NextResponse.json({ message }, { status: backendResponse.status });
  }

  const backendJob = unwrapBackendData<BackendJobResponse>(await backendResponse.json());
  return NextResponse.json(mapBackendJobToFrontend(backendJob, input), { status: 200 });
}
