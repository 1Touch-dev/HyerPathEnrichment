import { useQuery } from "@tanstack/react-query";
import { getPracticeSession } from "@/src/lib/api-client";
import { practiceKeys } from "../api/keys";

const POLL_INTERVAL_MS = 3000;

/**
 * Polls while any attempt still has a null score and no feedback. A null score
 * with feedback is terminal (scoring failed, or there was no text to score),
 * so those answers must not keep the report on "Pending...".
 */
export function usePracticeSession(sessionId: string | undefined) {
  return useQuery({
    queryKey: practiceKeys.session(sessionId ?? ""),
    queryFn: async () => (await getPracticeSession(sessionId!)).data,
    enabled: Boolean(sessionId),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const session = query.state.data;
      if (!session) return POLL_INTERVAL_MS;

      // A null score with feedback is terminal (scoring failed or there was
      // nothing to score). Keep polling only while a score is still expected.
      const hasPendingScore = session.attempts.some(
        (attempt) => attempt.aiScore === null && !attempt.aiFeedback,
      );
      return hasPendingScore ? POLL_INTERVAL_MS : false;
    },
  });
}
