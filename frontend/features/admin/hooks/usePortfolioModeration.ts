import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchAdminPortfolioProfile,
  fetchAdminPortfolioProfiles,
  moderatePortfolioProfile,
  type AdminPortfolioFilters,
} from "../api/client";
import { adminKeys } from "../api/keys";

export function useAdminPortfolioProfiles(
  cursor: string | null,
  filters: AdminPortfolioFilters = {},
) {
  return useQuery({
    queryKey: adminKeys.portfolio(cursor, filters),
    queryFn: () => fetchAdminPortfolioProfiles(cursor, filters),
  });
}

export function useAdminPortfolioProfile(profileId: string) {
  return useQuery({
    queryKey: adminKeys.portfolioProfile(profileId),
    queryFn: () => fetchAdminPortfolioProfile(profileId),
  });
}

export function useModeratePortfolioProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      profileId,
      adminHidden,
      reason,
    }: {
      profileId: string;
      adminHidden: boolean;
      reason?: string;
    }) => moderatePortfolioProfile(profileId, adminHidden, reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}
