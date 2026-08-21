import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchFailedJobs, fetchQueuesOverview, retryFailedJob } from "../api/client";
import { adminKeys } from "../api/keys";

export function useQueuesOverview() {
  return useQuery({
    queryKey: adminKeys.queues(),
    queryFn: fetchQueuesOverview,
    refetchInterval: 15_000, // Live-ish queue depth without a websocket, matches
    // this repo's existing polling convention for dashboard-style data.
  });
}

export function useFailedJobs(queueName: string) {
  return useQuery({
    queryKey: adminKeys.failedJobs(queueName),
    queryFn: () => fetchFailedJobs(queueName),
    enabled: !!queueName,
  });
}

export function useRetryFailedJob(queueName: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => retryFailedJob(queueName, jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.failedJobs(queueName) }),
  });
}
