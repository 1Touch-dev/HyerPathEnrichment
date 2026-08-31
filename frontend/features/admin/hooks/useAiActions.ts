import { useQuery } from "@tanstack/react-query";
import { fetchAiAction, fetchAiActions, type AiActionFilters } from "../api/client";
import { adminKeys } from "../api/keys";

export function useAiActions(cursor: string | null, filters: AiActionFilters = {}) {
  return useQuery({
    queryKey: adminKeys.aiActions(cursor, filters),
    queryFn: () => fetchAiActions(cursor, filters),
  });
}

export function useAiAction(id: string | null) {
  return useQuery({
    queryKey: adminKeys.aiAction(id ?? ""),
    queryFn: () => fetchAiAction(id!),
    enabled: !!id,
  });
}
