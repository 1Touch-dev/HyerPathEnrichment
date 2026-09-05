import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateApplicationStatus } from "../api/client";
import { applicationTrackerKeys } from "../api/keys";
import type { ApplicationStatus } from "@/src/lib/types";

export function useUpdateApplicationStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, status }: { matchId: string; status: ApplicationStatus }) =>
      updateApplicationStatus(matchId, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationTrackerKeys.all }),
  });
}
