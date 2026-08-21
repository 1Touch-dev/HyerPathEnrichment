import { useMutation, useQueryClient } from "@tanstack/react-query";
import { addPracticeAttempt } from "@/src/lib/api-client";
import { practiceKeys } from "../api/keys";

type AddAttemptInput = {
  sessionId: string;
  questionId?: string;
  responseType: "text" | "audio";
  textResponse?: string;
  audioRecordingId?: string;
  timeTakenSeconds?: number;
};

/** Mirrors `useCreatePracticeSession.ts`'s shape; invalidates the session detail so the new attempt shows up. */
export function useAddAttempt() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ sessionId, ...payload }: AddAttemptInput) =>
      (await addPracticeAttempt(sessionId, payload)).data,
    onSuccess: (_attempt, { sessionId }) => {
      void queryClient.invalidateQueries({ queryKey: practiceKeys.session(sessionId) });
    },
  });
}
