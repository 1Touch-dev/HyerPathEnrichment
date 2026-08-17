import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reprocessDocument } from "../api/client";
import { documentKeys } from "../api/keys";

export function useReprocessDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => reprocessDocument(documentId),
    onSuccess: (_data, documentId) => {
      queryClient.invalidateQueries({ queryKey: documentKeys.detail(documentId) });
    },
  });
}
