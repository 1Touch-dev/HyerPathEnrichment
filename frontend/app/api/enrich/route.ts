import { NextRequest, NextResponse } from 'next/server';
import { BackendJobResponse, mapBackendJobToFrontend, toBackendEnrichmentRequest } from '@/src/lib/api-adapter';
import { EnrichmentInput } from '@/src/lib/types';

export async function POST(request: NextRequest) {
  const body = (await request.json()) as Partial<EnrichmentInput>;

  const input: EnrichmentInput = {
    email: body.email?.trim() || '',
    linkedinUrl: body.linkedinUrl?.trim() || '',
    username: body.username?.trim() || '',
    company: body.company?.trim() || '',
    business: body.business?.trim() || '',
    jobSearch: body.jobSearch?.trim() || '',
    requestedTiers: body.requestedTiers?.length ? body.requestedTiers : ['tier1', 'tier2', 'tier3', 'tier4'],
  };

  const hasIdentifier = Boolean(
    input.email || input.linkedinUrl || input.username || input.company || input.business || input.jobSearch,
  );

  if (!hasIdentifier) {
    return NextResponse.json({ message: 'At least one identifier is required.' }, { status: 400 });
  }

  const backendUrl = process.env.BACKEND_API_URL ?? 'http://localhost:8000';
  const apiToken = process.env.BACKEND_API_TOKEN ?? 'change-me';

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${backendUrl}/enrich/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiToken}`,
      },
      body: JSON.stringify(toBackendEnrichmentRequest(input)),
    });
  } catch {
    return NextResponse.json({ message: 'Unable to reach enrichment backend.' }, { status: 502 });
  }

  if (!backendResponse.ok) {
    const detail = await backendResponse.text();
    let message = detail || 'Backend error';

    try {
      const parsed = JSON.parse(detail) as { detail?: string | Array<{ msg?: string }> };
      if (typeof parsed.detail === 'string') {
        message = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        message = parsed.detail.map((item) => item.msg).filter(Boolean).join(', ') || message;
      }
    } catch {
      // keep raw detail text
    }

    return NextResponse.json({ message }, { status: backendResponse.status });
  }

  const backendJob = (await backendResponse.json()) as BackendJobResponse;
  return NextResponse.json(mapBackendJobToFrontend(backendJob, input), { status: 200 });
}
