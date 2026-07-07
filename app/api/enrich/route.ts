import { NextRequest, NextResponse } from 'next/server';
import { createMockJob } from '@/src/lib/mock-data';
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

  return NextResponse.json(
    {
      ...createMockJob(input),
      metadata: {
        backendPath: '/backend',
        note: 'Frontend mock route remains for local UI preview; production backend now lives in the backend/ folder.',
      },
    },
    { status: 200 },
  );
}
