import { useQuery } from "@tanstack/react-query";
import { useRef } from "react";
import { fetchDocumentJob } from "../api/client";
import { documentKeys } from "../api/keys";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = ["completed", "failed", "duplicate"];

function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export function useDocumentJobQuery(jobId: string | undefined) {
  const terminalCheckDoneRef = useRef(false);

  return useQuery({
    queryKey: documentKeys.job(jobId ?? ""),
    queryFn: async () => {
      const job = await fetchDocumentJob(jobId!);

      // Reset terminal check flag when job status changes to non-terminal
      if (job && !isTerminalStatus(job.status)) {
        terminalCheckDoneRef.current = false;
      }

      return job;
    },
    enabled: Boolean(jobId),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job) return POLL_INTERVAL_MS;

      // If terminal status, do ONE more check then stop
      if (isTerminalStatus(job.status)) {
        if (terminalCheckDoneRef.current) {
          return false; // Stop polling
        } else {
          terminalCheckDoneRef.current = true;
          return POLL_INTERVAL_MS; // One more check
        }
      }

      return POLL_INTERVAL_MS;
    },
  });
}
