import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cancelInterview } from "../api/client";
import { interviewSchedulingKeys } from "../api/keys";

export function useCancelInterview(matchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => cancelInterview(matchId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: interviewSchedulingKeys.schedule(matchId) }),
  });
}
