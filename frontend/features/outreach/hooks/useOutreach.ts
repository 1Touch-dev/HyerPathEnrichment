import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { draftOutreach, editOutreachDraft, fetchOutreachMessages, sendOutreach } from "@/src/lib/api-client";
import { outreachKeys } from "../api/keys";

export function useOutreachMessages() {
  return useQuery({
    queryKey: outreachKeys.list(),
    queryFn: async () => (await fetchOutreachMessages()).data,
  });
}

export function useDraftOutreach() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobPostingId, documentId }: { jobPostingId: string; documentId?: string }) =>
      draftOutreach(jobPostingId, documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: outreachKeys.list() }),
  });
}

export function useEditOutreachDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, subject, body }: { messageId: string; subject: string; body: string }) =>
      editOutreachDraft(messageId, subject, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: outreachKeys.list() }),
  });
}

export function useSendOutreach() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) => sendOutreach(messageId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: outreachKeys.list() }),
  });
}
