import { useQuery } from "@tanstack/react-query";
import { fetchDocument } from "../api/client";
import { documentKeys } from "../api/keys";

export function useDocument(documentId: string | undefined) {
  return useQuery({
    queryKey: documentKeys.detail(documentId ?? ""),
    queryFn: () => fetchDocument(documentId!),
    enabled: Boolean(documentId),
  });
}
