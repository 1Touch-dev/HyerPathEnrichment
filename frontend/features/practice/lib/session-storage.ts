import { InterviewQuestion } from "@/src/lib/types";

/**
 * `POST /api/practice/questions` doesn't persist its result anywhere server-side outside
 * of the attempts a candidate eventually submits (backend/app/modules/questions has no
 * "session questions" join table) — so the generated question list has to travel from the
 * landing page to the session page some other way. `sessionStorage`, keyed by practice
 * session id, is the smallest mechanism that works within the same browser tab without
 * inventing new backend state; if the tab session is lost (e.g. a hard refresh on a
 * shared link), the session page's "generate questions" fallback path covers it.
 */
function storageKey(sessionId: string): string {
  return `practice:questions:${sessionId}`;
}

export function loadStoredQuestions(sessionId: string): InterviewQuestion[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.sessionStorage.getItem(storageKey(sessionId));
    return raw ? (JSON.parse(raw) as InterviewQuestion[]) : [];
  } catch {
    return [];
  }
}

export function storeQuestions(sessionId: string, questions: InterviewQuestion[]): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(storageKey(sessionId), JSON.stringify(questions));
  } catch {
    // Best-effort — falling back to the "generate questions" path if storage fails.
  }
}
