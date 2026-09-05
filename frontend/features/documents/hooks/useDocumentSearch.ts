import { useQuery } from "@tanstack/react-query";
import { searchDocuments } from "../api/client";
import { documentKeys } from "../api/keys";

export function useDocumentSearch(query: string, limit = 10) {
  return useQuery({
    queryKey: documentKeys.search(query, limit),
    queryFn: () => searchDocuments(query, limit),
    enabled: query.trim().length > 0,
  });
}
