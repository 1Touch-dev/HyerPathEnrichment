import { NextRequest, NextResponse } from 'next/server';
import { BackendJobResponse, mapBackendJobToFrontend, parseBackendError, unwrapBackendData } from '@/src/lib/api-adapter';
import { backendFetch } from '@/src/lib/backend-client';
import { EnrichmentInput } from '@/src/lib/types';
import { isMockMode } from '@/src/lib/mocks/enabled';
import { getMockJob } from '@/src/lib/mocks/mock-jobs';

export async function GET(_request: NextRequest, { params }: { params: { id: string } }) {
  if (isMockMode()) {
    const job = getMockJob(params.id);
    if (!job) {
      return NextResponse.json({ message: 'Job not found.' }, { status: 404 });
    }
    return NextResponse.json(job);
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/enrich/${params.id}`);
  } catch {
    return NextResponse.json({ message: 'Unable to reach enrichment backend.' }, { status: 502 });
  }

  if (!backendResponse.ok) {
    const message = await parseBackendError(backendResponse);
    return NextResponse.json({ message }, { status: backendResponse.status });
  }

  const backendJob = unwrapBackendData<BackendJobResponse>(await backendResponse.json());
  const input: EnrichmentInput = {
    email: '',
    linkedinUrl: '',
    username: '',
    company: '',
    business: '',
    jobSearch: '',
    requestedTiers: backendJob.dossier?.metadata ? [] : [],
  };

  const metadata = backendJob.dossier?.metadata as Record<string, unknown> | undefined;
  if (metadata) {
    const tiers = metadata.requested_tiers ?? metadata.requestedTiers;
    if (Array.isArray(tiers)) {
      input.requestedTiers = tiers.filter(
        (tier): tier is EnrichmentInput['requestedTiers'][number] =>
          tier === 'tier1' || tier === 'tier2' || tier === 'tier3' || tier === 'tier4',
      );
    }
    const summary = metadata.identifier_summary ?? metadata.identifierSummary;
    if (typeof summary === 'string' && summary) {
      input.username = summary;
    }
  }

  return NextResponse.json(mapBackendJobToFrontend(backendJob, input));
}
