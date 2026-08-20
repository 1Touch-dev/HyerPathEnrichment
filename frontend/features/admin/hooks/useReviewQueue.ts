import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { decideReviewQueueItem, fetchReviewQueue, fetchReviewQueueItem } from "../api/client";
import { adminKeys } from "../api/keys";

export function useReviewQueue(
  cursor: string | null,
  resourceType: string | null = null,
  status: string | null = null,
) {
  return useQuery({
    queryKey: adminKeys.reviewQueue(cursor, resourceType, status),
    queryFn: () => fetchReviewQueue(cursor, resourceType, status),
  });
}

export function useReviewQueueItem(id: string | null) {
  return useQuery({
    queryKey: adminKeys.reviewQueueItem(id ?? ""),
    queryFn: () => fetchReviewQueueItem(id!),
    enabled: !!id,
  });
}

export function useDecideReviewQueueItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
      reviewNotes,
    }: {
      id: string;
      status: "approved" | "rejected";
      reviewNotes?: string;
    }) => decideReviewQueueItem(id, status, reviewNotes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.reviewQueueAll() }),
  });
}
