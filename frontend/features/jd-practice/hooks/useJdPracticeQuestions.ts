import { useMutation } from "@tanstack/react-query";
import { requestJdPracticeQuestions } from "../api/client";

type UseJdPracticeQuestionsInput = {
  jobMatchId: string;
  category?: string;
  difficulty?: string;
  count?: number;
};

/**
 * A mutation, not a query — generating JD-tailored questions is a real, multi-second
 * LLM call with side effects (a new `PracticeSession` row, a daily-limit budget spend,
 * §9.4) and must never be served from cache or refetched implicitly. Mirrors
 * `useTriggerScan`'s (frontend/features/job-matching/hooks/useMatches.ts) and this
 * codebase's own `useQuestions`' (frontend/features/practice/hooks/useQuestions.ts)
 * existing "trigger an action, get a result" mutation shape.
 */
export function useJdPracticeQuestions() {
  return useMutation({
    mutationFn: ({ jobMatchId, category, difficulty, count }: UseJdPracticeQuestionsInput) =>
      requestJdPracticeQuestions(jobMatchId, category, difficulty, count),
  });
}
