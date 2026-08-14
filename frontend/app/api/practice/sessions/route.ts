import { NextRequest } from "next/server";
import { mapBackendPracticeSession, mapBackendPracticeSessionList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/** Thin proxy for the backend's `POST /sessions` (create_session, backend/app/modules/sessions/router.py). */
export async function POST(request: NextRequest) {
  const body = await request.json();
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendPracticeSession, 201);
}

/** Thin proxy for the backend's `GET /sessions` (list_sessions, backend/app/modules/sessions/router.py). */
export async function GET(request: NextRequest) {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/sessions${request.nextUrl.search}`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendPracticeSessionList);
}
