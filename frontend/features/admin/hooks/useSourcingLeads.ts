import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createLead,
  listLeads,
  reviewLead,
  type CreateSourcedLeadInput,
  type SourcedLeadStatus,
} from "../api/sourcing-leads-client";
import { adminKeys } from "../api/keys";

export function useSourcedLeads(status: SourcedLeadStatus | null = null) {
  return useQuery({
    queryKey: [...adminKeys.all, "sourcing-leads", status ?? "all"] as const,
    queryFn: () => listLeads(status),
  });
}

export function useCreateSourcedLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateSourcedLeadInput) => createLead(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}

export function useReviewSourcedLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: "reviewed" | "contacted" | "dismissed" }) =>
      reviewLead(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}
