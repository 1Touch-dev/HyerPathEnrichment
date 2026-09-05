import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { confirmMfaEnrollment, disableMfa, enrollMfa, fetchMfaStatus } from "../api/client";
import { adminKeys } from "../api/keys";

export function useMfaStatus() {
  return useQuery({ queryKey: adminKeys.mfaStatus(), queryFn: fetchMfaStatus });
}

export function useEnrollMfa() {
  return useMutation({ mutationFn: enrollMfa });
}

export function useConfirmMfaEnrollment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => confirmMfaEnrollment(code),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.mfaStatus() }),
  });
}

export function useDisableMfa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => disableMfa(code),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.mfaStatus() }),
  });
}
