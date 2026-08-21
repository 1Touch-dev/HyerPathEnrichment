import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AdminDocumentFilters, AdminDocumentModerateAction } from "@/src/lib/types";
import { fetchAdminDocument, fetchAdminDocuments, moderateDocument } from "../api/client";
import { adminKeys } from "../api/keys";

const DEFAULT_FILTERS: AdminDocumentFilters = { processingStatus: null, deleted: null };

export function useAdminDocuments(
  cursor: string | null,
  filters: AdminDocumentFilters = DEFAULT_FILTERS,
) {
  return useQuery({
    queryKey: adminKeys.documents(cursor, filters.processingStatus, filters.deleted),
    queryFn: () => fetchAdminDocuments(cursor, filters),
  });
}

export function useAdminDocument(id: string | null) {
  return useQuery({
    queryKey: adminKeys.document(id ?? ""),
    queryFn: () => fetchAdminDocument(id as string),
    enabled: !!id,
  });
}

export function useModerateDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      action,
      reason,
    }: {
      documentId: string;
      action: AdminDocumentModerateAction;
      reason?: string;
    }) => moderateDocument(documentId, action, reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}
