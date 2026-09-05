import { useQuery } from "@tanstack/react-query";
import { fetchCvCompleteness } from "@/src/lib/api-client";
import { cvManagementKeys } from "../api/keys";

export function useCvCompleteness(documentId: string | null) {
  return useQuery({
    queryKey: cvManagementKeys.completeness(documentId ?? ""),
    queryFn: async () => (await fetchCvCompleteness(documentId as string)).data,
    enabled: Boolean(documentId),
  });
}
