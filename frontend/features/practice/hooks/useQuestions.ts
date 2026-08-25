import { useMutation } from "@tanstack/react-query";
import { fetchQuestions } from "@/src/lib/api-client";

type FetchQuestionsInput = {
  jobRole: string;
  count?: number;
  category?: string;
  difficulty?: string;
  personalize?: boolean;
  documentId?: string;
};

/**
 * A mutation, not a query — `POST /api/practice/questions` has side effects (it may
 * generate and persist new personalized questions), matching this codebase's existing
 * convention of calling side-effecting POST endpoints via `useMutation`.
 */
export function useQuestions() {
  return useMutation({
    mutationFn: async (input: FetchQuestionsInput) => (await fetchQuestions(input)).data,
  });
}
