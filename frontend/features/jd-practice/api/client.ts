import { parseResponseEnvelopeError } from "@/src/lib/api-envelope";
import type { JdPracticeResponse } from "@/src/lib/types";

export type JdPracticeQuestionsInput = {
  jobMatchId?: string;
  jobDescription?: string;
  jobTitle?: string;
  company?: string;
  category?: string;
  difficulty?: string;
  count?: number;
  documentId?: string;
};

/**
 * Proxies to the BFF's `POST /api/jd-practice/questions`, which itself proxies to the
 * backend's `POST /api/jd-practice/questions` (backend/app/modules/jd_practice/router.py,
 * phase2_module4 §9.4, ADR 0018). Always triggers a fresh LLM generation call (JD-tailored
 * questions bypass the shared question bank entirely, §9.2) and creates a new
 * `PracticeSession` row — it is a generation request with side effects, not a cacheable
 * GET, so callers should drive it via a mutation hook (see `useJdPracticeQuestions`).
 *
 * Provide exactly one of `jobMatchId` or `jobDescription`.
 */
export async function requestJdPracticeQuestions(
  input: JdPracticeQuestionsInput,
): Promise<JdPracticeResponse> {
  const res = await fetch("/api/jd-practice/questions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    cache: "no-store",
    body: JSON.stringify({
      jobMatchId: input.jobMatchId ?? undefined,
      jobDescription: input.jobDescription ?? undefined,
      jobTitle: input.jobTitle ?? undefined,
      company: input.company ?? undefined,
      category: input.category ?? undefined,
      difficulty: input.difficulty ?? undefined,
      count: input.count ?? undefined,
      documentId: input.documentId ?? undefined,
    }),
  });

  if (!res.ok) {
    throw await parseResponseEnvelopeError(res);
  }

  const json = await res.json();
  return json.data as JdPracticeResponse;
}
