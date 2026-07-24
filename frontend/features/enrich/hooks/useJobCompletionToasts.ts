import { useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { jobKeys } from "@/features/history";
import { subscribeJobEvents } from "@/src/lib/enrich-events";
import { isTerminalStatus } from "@/src/lib/enrich-poll";
import { JobStatus } from "@/src/lib/types";
import { enrichKeys } from "../api/keys";

const TERMINAL_TOAST: Record<
  "completed" | "failed" | "suppressed",
  { title: string; kind: "success" | "error" | "info" }
> = {
  completed: { title: "Job completed", kind: "success" },
  failed: { title: "Job failed", kind: "error" },
  suppressed: { title: "Job suppressed", kind: "info" },
};

function showTerminalToast(status: JobStatus, jobId: string): void {
  const meta = TERMINAL_TOAST[status as keyof typeof TERMINAL_TOAST];
  if (!meta) return;

  toast[meta.kind](meta.title, {
    description: jobId,
    action: {
      label: "View Results",
      onClick: () => {
        window.location.href = `/app/jobs/${jobId}`;
      },
    },
    duration: 5000,
  });
}

/**
 * Subscribes to SSE completion events for async enrichment jobs and surfaces
 * a toast + query invalidation once each job reaches a terminal status.
 * Returns a `trackJob(jobId)` function to call right after job creation.
 */
export function useJobCompletionToasts(): (jobId: string) => void {
  const queryClient = useQueryClient();
  const unsubscribersRef = useRef(new Map<string, () => void>());

  useEffect(() => {
    const unsubscribers = unsubscribersRef.current;
    return () => {
      unsubscribers.forEach((unsubscribe) => unsubscribe());
      unsubscribers.clear();
    };
  }, []);

  return useCallback(
    (jobId: string) => {
      const unsubscribers = unsubscribersRef.current;
      if (unsubscribers.has(jobId)) return;

      const stop = () => {
        unsubscribers.get(jobId)?.();
        unsubscribers.delete(jobId);
      };

      const unsubscribe = subscribeJobEvents(jobId, {
        onStatus: (status) => {
          if (!isTerminalStatus(status)) return;
          showTerminalToast(status, jobId);
          void queryClient.invalidateQueries({ queryKey: enrichKeys.job(jobId) });
          void queryClient.invalidateQueries({ queryKey: enrichKeys.jobs() });
          void queryClient.invalidateQueries({ queryKey: jobKeys.all });
          stop();
        },
        // Transient network errors trigger EventSource's built-in reconnect;
        // only tear down the subscription once we've seen a terminal status.
      });

      unsubscribers.set(jobId, unsubscribe);
    },
    [queryClient],
  );
}
