import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  claimLinkedInTask,
  completeLinkedInTask,
  createLinkedInSendBatch,
  fetchLinkedInTasks,
  skipLinkedInTask,
  startLinkedInSendBatch,
} from "../api/client";
import { adminKeys } from "../api/keys";

export function useLinkedInTasks(status: string | null = null) {
  return useQuery({
    queryKey: adminKeys.linkedinTasks(status),
    queryFn: () => fetchLinkedInTasks(status),
  });
}

export function useClaimLinkedInTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => claimLinkedInTask(taskId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}

export function useCompleteLinkedInTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, outcomeNote }: { taskId: string; outcomeNote?: string | null }) =>
      completeLinkedInTask(taskId, outcomeNote),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}

export function useSkipLinkedInTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, outcomeNote }: { taskId: string; outcomeNote?: string | null }) =>
      skipLinkedInTask(taskId, outcomeNote),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}

export function useCreateLinkedInSendBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      multiloginProfileId: string;
      maxSendsPerDay: number;
      taskIds: string[];
    }) => createLinkedInSendBatch(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}

export function useStartLinkedInSendBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) => startLinkedInSendBatch(batchId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}
