import { useMutation, useQueryClient } from "@tanstack/react-query";
import { scheduleInterview, ScheduleInterviewInput } from "../api/client";
import { interviewSchedulingKeys } from "../api/keys";

export function useScheduleInterview(matchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ScheduleInterviewInput) => scheduleInterview(matchId, input),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: interviewSchedulingKeys.schedule(matchId) }),
  });
}
