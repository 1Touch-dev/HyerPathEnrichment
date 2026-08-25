import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  draftOutreach,
  editOutreachDraft,
  fetchOutreachMessages,
  sendOutreach,
} from "@/src/lib/api-client";
import type { OutreachMessageType } from "@/src/lib/types";
import { outreachKeys } from "../api/keys";

export function useOutreachMessages(options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: outreachKeys.list(),
    queryFn: async () => (await fetchOutreachMessages()).data,
    // Drafting is async (§8.13 enqueues an RQ job); briefly poll the list after a new
    // draft was requested so the generated message appears without a manual refresh.
    refetchInterval: options.poll ? 4_000 : false,
  });
}

export type DraftOutreachPayload = {
  companyName: string;
  documentId: string;
  recipientRoleTitle?: string;
  jobMatchId?: string;
  jobDescription?: string;
  messageType?: OutreachMessageType;
  customInstruction?: string;
};

export function useDraftOutreach() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DraftOutreachPayload) => draftOutreach(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: outreachKeys.list() }),
  });
}

/**
 * Draft from a job match (swipe deck). Callers must supply `documentId` from the
 * dialog's résumé picker — auto-picking the latest CV is no longer done here.
 */
export function useDraftOutreachForMatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DraftOutreachPayload) => draftOutreach(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: outreachKeys.list() }),
  });
}

export function useEditOutreachDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      messageId,
      subject,
      body,
    }: {
      messageId: string;
      subject: string;
      body: string;
    }) => editOutreachDraft(messageId, subject, body),
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
