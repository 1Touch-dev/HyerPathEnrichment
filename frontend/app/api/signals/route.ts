import { NextRequest, NextResponse } from 'next/server';
import {
  BackendSignalListResponse,
  mapBackendSignalListToFrontend,
  parseBackendError,
  unwrapBackendData,
} from '@/src/lib/api-adapter';
import { backendFetch } from '@/src/lib/backend-client';
import { isMockMode } from '@/src/lib/mocks/enabled';
import { listMockSignals } from '@/src/lib/mocks/mock-signals';

export async function GET(request: NextRequest) {
  const limit = Number(request.nextUrl.searchParams.get('limit') ?? '50');
  const offset = Number(request.nextUrl.searchParams.get('offset') ?? '0');

  if (isMockMode()) {
    return NextResponse.json(listMockSignals(limit, offset));
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/signals?limit=${limit}&offset=${offset}`);
  } catch {
    return NextResponse.json({ message: 'Unable to reach enrichment backend.' }, { status: 502 });
  }

  if (!backendResponse.ok) {
    const message = await parseBackendError(backendResponse);
    return NextResponse.json({ message }, { status: backendResponse.status });
  }

  const payload = unwrapBackendData<BackendSignalListResponse>(await backendResponse.json());
  return NextResponse.json(mapBackendSignalListToFrontend(payload));
}
