import { useQuery } from "@tanstack/react-query";
import { fetchFeatureFlags } from "../api/client";
import { adminKeys } from "../api/keys";

export function useFeatureFlags() {
  return useQuery({ queryKey: adminKeys.featureFlags(), queryFn: fetchFeatureFlags });
}
