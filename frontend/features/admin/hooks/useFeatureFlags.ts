import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchFeatureFlags, upsertFeatureFlag } from "../api/client";
import { adminKeys } from "../api/keys";
import type { FeatureFlag } from "@/src/lib/types";

export function useFeatureFlags() {
  return useQuery({ queryKey: adminKeys.featureFlags(), queryFn: fetchFeatureFlags });
}

export function useUpsertFeatureFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, payload }: { key: string; payload: Partial<FeatureFlag> }) =>
      upsertFeatureFlag(key, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.featureFlags() }),
  });
}
