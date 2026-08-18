import { useQuery } from "@tanstack/react-query";
import { fetchCvData } from "../api/client";
import { documentKeys } from "../api/keys";

export function useCvData(documentId: string | undefined) {
  return useQuery({
    queryKey: documentKeys.cvData(documentId ?? ""),
    queryFn: () => fetchCvData(documentId!),
    enabled: Boolean(documentId),
  });
}
