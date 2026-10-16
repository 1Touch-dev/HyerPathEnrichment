import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addPortfolioItem,
  deletePortfolioItem,
  fetchPortfolioProfile,
  publishPortfolioProfile,
  savePortfolioProfile,
} from "@/src/lib/api-client";
import type { PortfolioItem, PortfolioProfile } from "@/src/lib/types";
import { portfolioKeys } from "../api/keys";

export function usePortfolioProfile() {
  return useQuery({
    queryKey: portfolioKeys.profile(),
    queryFn: async () => (await fetchPortfolioProfile()).data,
    retry: (failureCount, error) => {
      if (error instanceof Error && error.message.includes("404")) return false; // not created yet
      return failureCount < 2;
    },
  });
}

export function useSavePortfolioProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<PortfolioProfile> & { slug: string; publish?: boolean }) =>
      savePortfolioProfile(payload),
    onSuccess: (response) => queryClient.setQueryData(portfolioKeys.profile(), response.data),
  });
}

export function usePublishPortfolioProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => publishPortfolioProfile(),
    onSuccess: (response) => queryClient.setQueryData(portfolioKeys.profile(), response.data),
  });
}

export function useAddPortfolioItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Omit<PortfolioItem, "itemId" | "displayOrder">) =>
      addPortfolioItem(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: portfolioKeys.profile() }),
  });
}

export function useDeletePortfolioItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => deletePortfolioItem(itemId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: portfolioKeys.profile() }),
  });
}
