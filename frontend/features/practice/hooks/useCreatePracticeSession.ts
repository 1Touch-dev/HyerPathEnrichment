import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createPracticeSession } from "@/src/lib/api-client";
import { practiceKeys } from "../api/keys";

type CreatePracticeSessionInput = {
  sessionType: string;
  metadata?: Record<string, unknown>;
};

export function useCreatePracticeSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ sessionType, metadata }: CreatePracticeSessionInput) =>
      (await createPracticeSession(sessionType, metadata)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: practiceKeys.sessions() });
    },
  });
}
