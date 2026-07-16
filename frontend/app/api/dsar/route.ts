import { NextRequest, NextResponse } from 'next/server';
import { mapBackendDsarResponse, parseBackendError, toBackendDsarRequest } from '@/src/lib/api-adapter';
import { backendFetch } from '@/src/lib/backend-client';
import { DsarInput } from '@/src/lib/types';
import { isMockMode } from '@/src/lib/mocks/enabled';

export async function POST(request: NextRequest) {
  const body = (await request.json()) as DsarInput;

  if (!body.identifier?.trim()) {
    return NextResponse.json({ message: 'Identifier is required.' }, { status: 400 });
  }

  if (!body.requestType) {
    return NextResponse.json({ message: 'Request type is required.' }, { status: 400 });
  }

  if (isMockMode()) {
    return NextResponse.json(
      {
        id: `dsar_${Date.now()}`,
        status: 'completed',
        requestType: body.requestType,
        createdAt: new Date().toISOString(),
        completedAt: new Date().toISOString(),
        summary: { recordsFound: 0, recordsDeleted: body.requestType === 'deletion' ? 0 : undefined, mock: true },
      },
      { status: 201 },
    );
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch('/api/dsar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(toBackendDsarRequest(body)),
    });
  } catch {
    return NextResponse.json({ message: 'Unable to reach enrichment backend.' }, { status: 502 });
  }

  if (!backendResponse.ok) {
    const message = await parseBackendError(backendResponse);
    return NextResponse.json({ message }, { status: backendResponse.status });
  }

  const payload = mapBackendDsarResponse(await backendResponse.json());
  return NextResponse.json(payload, { status: 201 });
}
