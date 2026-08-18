import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchPreferences, updatePreferences } from "../api/client";
import { jobMatchingKeys } from "../api/keys";
import type { CandidateJobPreferences } from "@/src/lib/types";

export function usePreferences() {
  return useQuery({
    queryKey: jobMatchingKeys.preferences(),
    queryFn: fetchPreferences,
    retry: (failureCount, error) => {
      // 404 means "not set yet" — a valid state, not a retryable error.
      if (error instanceof Error && error.message.includes("404")) return false;
      return failureCount < 2;
    },
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<CandidateJobPreferences>) => updatePreferences(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(jobMatchingKeys.preferences(), data);
    },
  });
}
