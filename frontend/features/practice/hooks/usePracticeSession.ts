import { useQuery } from "@tanstack/react-query";
import { getPracticeSession } from "@/src/lib/api-client";
import { practiceKeys } from "../api/keys";

const POLL_INTERVAL_MS = 3000;

/**
 * Polls while any attempt in the session still has a `null` `aiScore` (i.e. its RQ
 * scoring job hasn't finished yet), mirroring `useJobQuery.ts`'s conditional
 * `refetchInterval`-function pattern adapted from "poll until terminal status" to
 * "poll until every attempt has been scored".
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

      const hasPendingScore = session.attempts.some((attempt) => attempt.aiScore === null);
      return hasPendingScore ? POLL_INTERVAL_MS : false;
    },
  });
}
