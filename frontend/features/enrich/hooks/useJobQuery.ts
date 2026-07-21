import { useQuery } from "@tanstack/react-query";
import { getEnrichmentJob } from "@/src/lib/api-client";
import { isTerminalStatus } from "@/src/lib/enrich-poll";
import { JobPendingError, isJobPendingError } from "../api/job-pending-error";
import { enrichKeys } from "../api/keys";

const POLL_INTERVAL_MS = 2000;

export function useJobQuery(jobId: string | undefined) {
  return useQuery({
    queryKey: enrichKeys.job(jobId ?? ""),
    queryFn: async () => {
      const job = (await getEnrichmentJob(jobId!)).data;
      if (!isTerminalStatus(job.status)) {
        throw new JobPendingError();
      }
      return job;
    },
    enabled: Boolean(jobId),
    staleTime: 0,
    refetchOnMount: "always",
    retry: (failureCount, error) => {
      if (isJobPendingError(error)) {
        return true;
      }
      return failureCount < 1;
    },
    retryDelay: (attemptIndex, error) => {
      if (isJobPendingError(error)) {
        return POLL_INTERVAL_MS;
      }
      return Math.min(1000 * 2 ** attemptIndex, 30_000);
    },
  });
}
