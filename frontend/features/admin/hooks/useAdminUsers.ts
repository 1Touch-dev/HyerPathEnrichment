import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assignUserRole, fetchAdminUsers, updateUserStatus } from "../api/client";
import { adminKeys } from "../api/keys";

export function useAdminUsers(cursor: string | null, isActive: boolean | null = null) {
  return useQuery({
    queryKey: adminKeys.users(cursor, isActive),
    queryFn: () => fetchAdminUsers(cursor, isActive),
  });
}

export function useUpdateUserStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      userId,
      isActive,
      reason,
    }: {
      userId: string;
      isActive: boolean;
      reason?: string;
    }) => updateUserStatus(userId, isActive, reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}

export function useAssignUserRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string | null }) =>
      assignUserRole(userId, roleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}
