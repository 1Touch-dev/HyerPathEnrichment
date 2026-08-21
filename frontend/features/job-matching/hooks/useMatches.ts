import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchMatches,
  markApplied,
  markMatchViewed,
  submitMatchFeedback,
  triggerScan,
} from "../api/client";
import { jobMatchingKeys } from "../api/keys";

export function useMatches(limit = 20, offset = 0) {
  return useQuery({
    queryKey: jobMatchingKeys.matches(limit, offset),
    queryFn: () => fetchMatches(limit, offset),
    refetchInterval: 60_000, // poll every 60s — matches are produced async by the worker
  });
}

export function useMarkMatchViewed() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (matchId: string) => markMatchViewed(matchId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobMatchingKeys.all }),
  });
}

export function useSubmitFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, feedback }: { matchId: string; feedback: "up" | "down" }) =>
      submitMatchFeedback(matchId, feedback),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobMatchingKeys.all }),
  });
}

export function useMarkApplied() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, applied }: { matchId: string; applied: boolean }) =>
      markApplied(matchId, applied),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobMatchingKeys.all }),
  });
}

export function useTriggerScan() {
  return useMutation({ mutationFn: triggerScan });
}
