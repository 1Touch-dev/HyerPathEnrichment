import { NextRequest, NextResponse } from 'next/server';
import {
  BackendJobListResponse,
  mapBackendJobListToFrontend,
  parseBackendError,
  unwrapBackendData,
} from '@/src/lib/api-adapter';
import { backendFetch } from '@/src/lib/backend-client';
import { isMockMode } from '@/src/lib/mocks/enabled';
import { listMockJobs } from '@/src/lib/mocks/mock-jobs';

export async function GET(request: NextRequest) {
  const limit = Number(request.nextUrl.searchParams.get('limit') ?? '50');
  const offset = Number(request.nextUrl.searchParams.get('offset') ?? '0');

  if (isMockMode()) {
    const { jobs, total } = listMockJobs(limit, offset);
    return NextResponse.json({ jobs, total, limit, offset });
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/enrich?limit=${limit}&offset=${offset}`);
  } catch {
    return NextResponse.json({ message: 'Unable to reach enrichment backend.' }, { status: 502 });
  }

  if (!backendResponse.ok) {
    const message = await parseBackendError(backendResponse);
    return NextResponse.json({ message }, { status: backendResponse.status });
  }

  const payload = unwrapBackendData<BackendJobListResponse>(await backendResponse.json());
  return NextResponse.json(mapBackendJobListToFrontend(payload));
}
