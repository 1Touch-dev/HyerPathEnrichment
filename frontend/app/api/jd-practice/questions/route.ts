import { NextRequest } from "next/server";
import { BackendJdPracticeResponse, mapBackendJdPracticeResponse } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

function parseCount(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

/**
 * Thin proxy for the backend's `POST /api/jd-practice/questions`
 * (backend/app/modules/jd_practice/router.py, phase2_module4 §9.4, ADR 0018). Always generates
 * fresh (bank-bypass, §9.2) and returns a new `practice_session_id` — on the backend's
 * daily-limit violation this surfaces as a 429 `RateLimitError` (backend/app/core/errors.py),
 * passed through unchanged by `handleBackendJson`/`backendFailureResponse` so the frontend
 * mutation hook receives an `ApiError` with `code === "RATE_LIMIT_EXCEEDED"`.
 *
 * Accepts exactly one of `jobMatchId` or `jobDescription`.
 */
export async function POST(request: NextRequest) {
  const body = await request.json();

  const jobMatchId =
    typeof body?.jobMatchId === "string" && body.jobMatchId.trim()
      ? body.jobMatchId.trim()
      : undefined;
  const jobDescription =
    typeof body?.jobDescription === "string" && body.jobDescription.trim()
      ? body.jobDescription.trim()
      : undefined;

  if (Boolean(jobMatchId) === Boolean(jobDescription)) {
    return bffValidationError("Provide exactly one of jobMatchId or jobDescription.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      "/api/jd-practice/questions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_match_id: jobMatchId,
          job_description: jobDescription,
          job_title: body.jobTitle ?? undefined,
          company: body.company ?? undefined,
          category: body.category ?? undefined,
          difficulty: body.difficulty ?? undefined,
          count: typeof body.count === "number" ? body.count : parseCount(body.count),
          document_id: body.documentId ?? undefined,
        }),
      },
      // LLM-backed question generation can take up to ~a minute; the global
      // 30s default is too tight for this route specifically.
      120_000,
    );
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendJdPracticeResponse) =>
    mapBackendJdPracticeResponse(payload),
  );
}
