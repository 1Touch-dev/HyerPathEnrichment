import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { draftOutreach, editOutreachDraft, fetchOutreachMessages, sendOutreach } from "@/src/lib/api-client";
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

export function useDraftOutreach() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      companyName: string;
      documentId: string;
      recipientRoleTitle?: string;
      jobMatchId?: string;
    }) => draftOutreach(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: outreachKeys.list() }),
  });
}

interface DocumentSummary {
  documentId: string;
  processingStatus: string;
  createdAt: string;
}

async function fetchMostRecentCompletedDocumentId(): Promise<string> {
  const res = await fetch("/api/documents", { credentials: "include", cache: "no-store" });
  if (!res.ok) {
    throw new Error("Could not load your documents.");
  }
  const json = await res.json();
  const documents: DocumentSummary[] = Array.isArray(json.data) ? json.data : [];
  const completed = documents
    .filter((d) => d.processingStatus === "completed")
    .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  if (completed.length === 0) {
    throw new Error("Upload and finish processing a CV before drafting outreach.");
  }
  return completed[0].documentId;
}

/**
 * Convenience wrapper for triggering a draft from a job match (e.g. the swipe deck's
 * "Draft outreach" button, phase2_module2.md §13.5) where the caller only has
 * `companyName`/`jobMatchId`, not a `documentId` — resolves the candidate's most
 * recently completed CV automatically via `GET /api/documents` rather than requiring a
 * CV-picker UI that does not exist yet (no `/app/documents` list route has been built —
 * see phase2_module2.md §13.2's own scope note).
 */
export function useDraftOutreachForMatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { companyName: string; jobMatchId?: string; recipientRoleTitle?: string }) => {
      const documentId = await fetchMostRecentCompletedDocumentId();
      return draftOutreach({ ...payload, documentId });
    },
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
