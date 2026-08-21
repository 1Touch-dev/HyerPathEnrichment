import { NextRequest } from "next/server";
import { mapBackendQuestionAttempt } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/** Thin proxy for the backend's `POST /sessions/{session_id}/attempts` (add_attempt, backend/app/modules/sessions/router.py). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await request.json();
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/sessions/${id}/attempts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendQuestionAttempt, 201);
}
