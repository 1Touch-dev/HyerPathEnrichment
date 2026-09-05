import { useMutation, useQueryClient } from "@tanstack/react-query";
import { applicationTrackerKeys } from "@/features/application-tracker/api/keys";
import { createManualJobEntry, CreateManualJobEntryInput } from "../api/client";

export function useCreateManualJobEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateManualJobEntryInput) => createManualJobEntry(input),
    onSuccess: () =>
      // Invalidate the tracker's list query so the new manual entry (and its
      // auto-created JobMatch row) appears immediately without a page refresh.
      queryClient.invalidateQueries({ queryKey: applicationTrackerKeys.all }),
  });
}
