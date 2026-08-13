import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { acceptCvBullet, fetchCvFeedback, requestCvFeedback } from "@/src/lib/api-client";
import { cvManagementKeys } from "../api/keys";

export function useCvFeedback(documentId: string, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: cvManagementKeys.feedback(documentId),
    queryFn: async () => (await fetchCvFeedback(documentId)).data,
    // Feedback runs on QUEUE_FEEDBACK asynchronously (§8.9) — poll until terminal.
    refetchInterval: (query) => {
      if (!options.poll) return false;
      const status = query.state.data?.status;
      return status === "pending" || status === "processing" ? 3_000 : false;
    },
  });
}

export function useRequestCvFeedback(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetRole?: string) => requestCvFeedback(documentId, targetRole),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cvManagementKeys.feedback(documentId) }),
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
