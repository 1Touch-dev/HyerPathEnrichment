import { NextRequest } from "next/server";
import { mapBackendQuestionListResponse } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/** Thin proxy for the backend's `POST /api/questions` (list_questions, backend/app/modules/questions/router.py). */
export async function POST(request: NextRequest) {
  const body = await request.json();
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/questions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendQuestionListResponse);
}
