import { useQuery } from "@tanstack/react-query";
import { fetchDocuments } from "../api/client";
import { documentKeys } from "../api/keys";

export function useDocuments(limit = 50) {
  return useQuery({
    queryKey: documentKeys.list(limit),
    queryFn: () => fetchDocuments(limit),
  });
}
