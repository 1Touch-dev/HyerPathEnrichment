import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteDocument } from "../api/client";
import { documentKeys } from "../api/keys";

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => deleteDocument(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentKeys.list() });
    },
  });
}
