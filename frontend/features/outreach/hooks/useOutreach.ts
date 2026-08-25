import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  draftOutreach,
  editOutreachDraft,
  fetchOutreachMessages,
  getCompanyTier,
  sendOutreach,
  setCompanyTier,
} from "@/src/lib/api-client";
import type {
  OutreachCompanyTierValue,
  OutreachMessageType,
  OutreachRoleType,
  OutreachSeniority,
  OutreachStrategy,
} from "@/src/lib/types";
import { outreachKeys } from "../api/keys";

// machine-2/03: company-tier query keys live alongside `outreachKeys` (not added
// to `api/keys.ts` itself, since that file is out of this chunk's edit scope) but
// follow the same `[...outreachKeys.all, ...]` nesting convention.
const companyTierKeys = {
  detail: (companyName: string) => [...outreachKeys.all, "companyTier", companyName] as const,
};

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
  strategy?: OutreachStrategy;
  referralContext?: string;
  roleType?: OutreachRoleType;
  seniority?: OutreachSeniority;
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

/**
 * machine-2/03: reads the recruiter's manually-set `EmployerCompanyTier` for a given
 * employer, so it persists/pre-fills across every future draft to the same company
 * (rather than re-asking per-draft). Disabled while `companyName` is empty — mirrors
 * the guard other per-entity queries in this codebase use for an not-yet-known id.
 */
export function useCompanyTier(companyName: string | null | undefined) {
  return useQuery({
    queryKey: companyTierKeys.detail(companyName ?? ""),
    queryFn: async () => (await getCompanyTier(companyName as string)).data,
    enabled: Boolean(companyName && companyName.trim()),
  });
}

export function useSetCompanyTier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      companyName,
      tier,
      notes,
    }: {
      companyName: string;
      tier: OutreachCompanyTierValue;
      notes?: string;
    }) => setCompanyTier(companyName, tier, notes),
    onSuccess: (_data, variables) =>
      queryClient.invalidateQueries({ queryKey: companyTierKeys.detail(variables.companyName) }),
  });
}
