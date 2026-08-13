import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/src/lib/api-envelope";
import {
  acceptCvBullet,
  fetchCvFeedback,
  fetchDocumentJobStatus,
  requestCvFeedback,
} from "@/src/lib/api-client";
import { cvManagementKeys } from "../api/keys";

const TERMINAL_JOB_STATUSES = new Set(["completed", "failed"]);

export function useCvFeedback(documentId: string) {
  return useQuery({
    queryKey: cvManagementKeys.feedback(documentId),
    queryFn: async () => {
      try {
        return (await fetchCvFeedback(documentId)).data;
      } catch (error) {
        // No interim "pending" row exists on `CvFeedbackReport` (Decision 3,
        // backend/app/workers/tasks/cv_improvement.py) — the backend 404s until
        // generation is fully complete, so a 404 here just means "no report yet",
        // not an error. Whether generation is in flight is tracked separately via
        // `useCvFeedbackJobStatus`, driven off the real job id.
        if (error instanceof ApiError && error.statusCode === 404) {
          return null;
        }
        throw error;
      }
    },
  });
}

/**
 * Polls the real async-job-status endpoint (JobStatusResponse) for a CV-feedback
 * generation job until it reaches a terminal state (completed/failed). Callers pass
 * the `jobId` returned by `useRequestCvFeedback`'s mutation and should invalidate
 * `cvManagementKeys.feedback(documentId)` once `status` becomes `"completed"`.
 */
export function useCvFeedbackJobStatus(jobId: string | null) {
  return useQuery({
    queryKey: cvManagementKeys.feedbackJob(jobId ?? "none"),
    queryFn: async () => (await fetchDocumentJobStatus(jobId as string)).data,
    enabled: Boolean(jobId),
    refetchInterval: (query) => (TERMINAL_JOB_STATUSES.has(query.state.data?.status ?? "") ? false : 3_000),
  });
}

export function useRequestCvFeedback(documentId: string) {
  return useMutation({
    // Unwraps the envelope so callers get `{ jobId }` directly from `mutate(...)`'s
    // per-call `onSuccess` — the real signal to start polling `useCvFeedbackJobStatus`.
    mutationFn: async (targetRole?: string) => (await requestCvFeedback(documentId, targetRole)).data,
  });
}

export function useAcceptCvBullet(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reportId, bulletIndex }: { reportId: string; bulletIndex: number }) =>
      acceptCvBullet(documentId, reportId, bulletIndex),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cvManagementKeys.feedback(documentId) }),
  });
}
