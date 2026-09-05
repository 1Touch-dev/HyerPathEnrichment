import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchAdminJobPosting,
  fetchAdminJobPostings,
  moderateJobPosting,
  type JobPostingFilters,
} from "../api/client";
import { adminKeys } from "../api/keys";
import type { ModerationStatus } from "@/src/lib/types";

export function useAdminJobPostings(cursor: string | null, filters: JobPostingFilters = {}) {
  return useQuery({
    queryKey: adminKeys.jobPostings(cursor, filters),
    queryFn: () => fetchAdminJobPostings(cursor, filters),
  });
}

export function useAdminJobPosting(id: string) {
  return useQuery({
    queryKey: adminKeys.jobPosting(id),
    queryFn: () => fetchAdminJobPosting(id),
    enabled: !!id,
  });
}

export function useModerateJobPosting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      moderationStatus,
      reason,
    }: {
      id: string;
      moderationStatus: ModerationStatus;
      reason?: string;
    }) => moderateJobPosting(id, moderationStatus, reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}
