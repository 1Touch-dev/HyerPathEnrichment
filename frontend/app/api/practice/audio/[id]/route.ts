import { NextRequest } from "next/server";
import { mapBackendAudioStatusResponse } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/** Thin proxy for the backend's `GET /api/practice/audio/{recording_id}` (get_audio_status, backend/app/modules/practice_audio/router.py). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/practice/audio/${id}`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendAudioStatusResponse);
}
