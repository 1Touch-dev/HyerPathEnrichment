import { useQuery } from "@tanstack/react-query";
import { fetchInterviewSchedule } from "../api/client";
import { interviewSchedulingKeys } from "../api/keys";

export function useInterviewSchedule(matchId: string) {
  return useQuery({
    queryKey: interviewSchedulingKeys.schedule(matchId),
    queryFn: () => fetchInterviewSchedule(matchId),
  });
}
