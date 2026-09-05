import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { endImpersonation, fetchImpersonationStatus, startImpersonation } from "../api/client";
import { adminKeys } from "../api/keys";

export function useImpersonationStatus() {
  return useQuery({
    queryKey: adminKeys.impersonationStatus(),
    queryFn: fetchImpersonationStatus,
    // Polled (not SSE) — impersonation-active is a rare, session-scoped state;
    // a dedicated real-time channel for it would be over-engineering relative
    // to a cheap 30s poll, unlike job-match unread counts which are high-frequency.
    refetchInterval: 30_000,
  });
}

export function useStartImpersonation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      userId,
      reason,
      mfaCode,
    }: {
      userId: string;
      reason: string;
      mfaCode?: string;
    }) => startImpersonation(userId, reason, mfaCode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.impersonationStatus() }),
  });
}

export function useEndImpersonation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: endImpersonation,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.impersonationStatus() }),
  });
}
