import { NextRequest } from "next/server";
import { mapBackendQuestionListResponse } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

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

/** Thin proxy for the backend's `POST /api/questions` (list_questions, backend/app/modules/questions/router.py). */
export async function POST(request: NextRequest) {
  const body = await request.json();
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      "/api/questions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_role: body.job_role ?? body.jobRole,
          category: body.category ?? undefined,
          difficulty: body.difficulty ?? undefined,
          count: parseCount(body.count),
          personalize: body.personalize ?? undefined,
          document_id: body.document_id ?? body.documentId ?? undefined,
        }),
      },
      // Multiple LLM batches (up to 3×5 questions) can exceed the default 30s.
      120_000,
    );
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendQuestionListResponse);
}
