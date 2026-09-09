import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { applicationTrackerKeys } from "@/features/application-tracker/api/keys";
import { jobSwipeKeys } from "@/features/job-swipe/api/keys";
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

type AppliedItem = { matchId: string; appliedAt: string | null };

function patchAppliedAt<T>(old: T, matchId: string, applied: boolean): T {
  if (!old || typeof old !== "object") return old;
  const appliedAt = applied ? new Date().toISOString() : null;
  const record = old as { matches?: AppliedItem[]; cards?: AppliedItem[] };
  if (Array.isArray(record.matches)) {
    return {
      ...record,
      matches: record.matches.map((item) =>
        item.matchId === matchId ? { ...item, appliedAt } : item,
      ),
    } as T;
  }
  if (Array.isArray(record.cards)) {
    return {
      ...record,
      cards: record.cards.map((item) => (item.matchId === matchId ? { ...item, appliedAt } : item)),
    } as T;
  }
  return old;
}

export function useMarkApplied() {
  const queryClient = useQueryClient();
  const appliedQueryKeys = [jobMatchingKeys.all, applicationTrackerKeys.all, jobSwipeKeys.all];

  return useMutation({
    mutationFn: ({ matchId, applied }: { matchId: string; applied: boolean }) =>
      markApplied(matchId, applied),
    onMutate: async ({ matchId, applied }) => {
      await Promise.all(
        appliedQueryKeys.map((queryKey) => queryClient.cancelQueries({ queryKey })),
      );
      const snapshots = appliedQueryKeys.map((queryKey) =>
        queryClient.getQueriesData({ queryKey }),
      );
      for (const queryKey of appliedQueryKeys) {
        queryClient.setQueriesData({ queryKey }, (old) => patchAppliedAt(old, matchId, applied));
      }
      return { snapshots };
    },
    onError: (_error, _variables, context) => {
      context?.snapshots.forEach((entries) => {
        entries.forEach(([key, data]) => queryClient.setQueryData(key, data));
      });
    },
    onSettled: () => {
      appliedQueryKeys.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }));
    },
  });
}

export function useTriggerScan() {
  return useMutation({ mutationFn: triggerScan });
}
