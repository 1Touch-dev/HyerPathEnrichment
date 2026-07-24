import { useQuery } from "@tanstack/react-query";
import { getEnrichmentJob } from "@/src/lib/api-client";
import { isTerminalStatus } from "@/src/lib/enrich-poll";
import { enrichKeys } from "../api/keys";

const POLL_INTERVAL_MS = 2000;

export function useJobQuery(jobId: string | undefined) {
  return useQuery({
    queryKey: enrichKeys.job(jobId ?? ""),
    queryFn: async () => {
      const job = (await getEnrichmentJob(jobId!)).data;
      return job;
    },
    enabled: Boolean(jobId),
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: (query) => {
      return query.state.data && !isTerminalStatus(query.state.data.status)
        ? POLL_INTERVAL_MS
        : false;
    },
  });
}
