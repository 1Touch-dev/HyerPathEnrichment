import { useQuery } from "@tanstack/react-query";
import { fetchPublicPortfolio } from "@/src/lib/api-client";
import { portfolioKeys } from "../api/keys";

export function usePublicPortfolio(slug: string) {
  return useQuery({
    queryKey: portfolioKeys.public(slug),
    queryFn: async () => (await fetchPublicPortfolio(slug)).data,
    retry: false, // 404 (unpublished/unknown slug) is a valid terminal state, not transient
  });
}
