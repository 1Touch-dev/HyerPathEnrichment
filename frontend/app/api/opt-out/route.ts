import { NextRequest, NextResponse } from 'next/server';
import { parseBackendError, toBackendOptOutRequest } from '@/src/lib/api-adapter';
import { backendFetch } from '@/src/lib/backend-client';
import { isMockMode } from '@/src/lib/mocks/enabled';
import { OptOutInput } from '@/src/lib/types';

export async function POST(request: NextRequest) {
  const body = (await request.json()) as OptOutInput;

  if (!body.identifier?.trim()) {
    return NextResponse.json({ message: 'Identifier is required.' }, { status: 400 });
  }

  if (isMockMode()) {
    return NextResponse.json({ status: 'accepted' }, { status: 202 });
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch('/api/opt-out', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(toBackendOptOutRequest(body)),
    });
  } catch {
    return NextResponse.json({ message: 'Unable to reach enrichment backend.' }, { status: 502 });
  }

  if (!backendResponse.ok) {
    const message = await parseBackendError(backendResponse);
    return NextResponse.json({ message }, { status: backendResponse.status });
  }

  return NextResponse.json({ status: 'accepted' }, { status: 202 });
}
