import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AdminOutreachFilters,
  fetchAdminOutreachMessage,
  fetchAdminOutreachMessages,
  moderateOutreachMessage,
} from "../api/client";
import { adminKeys } from "../api/keys";

export function useAdminOutreachMessages(
  cursor: string | null,
  filters: AdminOutreachFilters = {},
) {
  return useQuery({
    queryKey: adminKeys.outreach(cursor, filters.status ?? null, filters.adminBlocked ?? null),
    queryFn: () => fetchAdminOutreachMessages(cursor, filters),
  });
}

export function useAdminOutreachMessage(id: string) {
  return useQuery({
    queryKey: adminKeys.outreachMessage(id),
    queryFn: () => fetchAdminOutreachMessage(id),
  });
}

export function useModerateOutreachMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      adminBlocked,
      reason,
    }: {
      id: string;
      adminBlocked: boolean;
      reason?: string;
    }) => moderateOutreachMessage(id, adminBlocked, reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}
