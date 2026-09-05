import { NextRequest } from "next/server";
import { mapBackendPracticeSession } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/** Thin proxy for the backend's `GET /sessions/{session_id}` (get_session, backend/app/modules/sessions/router.py). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/sessions/${id}`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendPracticeSession);
}
