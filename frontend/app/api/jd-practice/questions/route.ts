import { NextRequest } from "next/server";
import { BackendJdPracticeResponse, mapBackendJdPracticeResponse } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/**
 * Thin proxy for the backend's `POST /api/jd-practice/questions`
 * (backend/app/modules/jd_practice/router.py, phase2_module4 §9.4). Always generates
 * fresh (bank-bypass, §9.2) and returns a new `practice_session_id` — on the backend's
 * daily-limit violation this surfaces as a 429 `RateLimitError` (backend/app/core/errors.py),
 * passed through unchanged by `handleBackendJson`/`backendFailureResponse` so the frontend
 * mutation hook receives an `ApiError` with `code === "RATE_LIMIT_EXCEEDED"`.
 */
export async function POST(request: NextRequest) {
  const body = await request.json();

  if (typeof body?.jobMatchId !== "string" || !body.jobMatchId.trim()) {
    return bffValidationError("jobMatchId is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      "/api/jd-practice/questions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_match_id: body.jobMatchId,
          category: body.category ?? undefined,
          difficulty: body.difficulty ?? undefined,
          count: body.count ?? undefined,
        }),
      },
      // LLM-backed question generation can take up to ~a minute; the global
      // 30s default is too tight for this route specifically.
      60_000,
    );
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendJdPracticeResponse) =>
    mapBackendJdPracticeResponse(payload),
  );
}
