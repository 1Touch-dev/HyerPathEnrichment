import { NextResponse } from 'next/server';
import { BackendHealthResponse, mapBackendHealth, unwrapBackendData } from '@/src/lib/api-adapter';
import { backendFetch } from '@/src/lib/backend-client';
import { isMockMode } from '@/src/lib/mocks/enabled';

export async function GET() {
  if (isMockMode()) {
    return NextResponse.json({ status: 'ok', service: 'hyrepath-enrichment-mock' });
  }

  try {
    const backendResponse = await backendFetch('/health');
    if (!backendResponse.ok) {
      return NextResponse.json({ status: 'error', service: 'hyrepath-enrichment' }, { status: 502 });
    }
    const payload = unwrapBackendData<BackendHealthResponse>(await backendResponse.json());
    return NextResponse.json(mapBackendHealth(payload));
  } catch {
    return NextResponse.json({ status: 'error', service: 'hyrepath-enrichment' }, { status: 502 });
  }
}
