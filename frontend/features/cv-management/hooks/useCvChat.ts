import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { postCvChatMessage, startCvChatSession } from "@/src/lib/api-client";
import type { CvChatSession } from "@/src/lib/types";
import { cvManagementKeys } from "../api/keys";

export function useCvChat(documentId: string) {
  const [session, setSession] = useState<CvChatSession | null>(null);
  const queryClient = useQueryClient();

  const start = useMutation({
    mutationFn: async () => (await startCvChatSession(documentId)).data,
    onSuccess: setSession,
  });

  const sendMessage = useMutation({
    mutationFn: async (content: string) => {
      if (!session) throw new Error("No active chat session.");
      return (await postCvChatMessage(session.sessionId, content)).data;
    },
    onSuccess: (updated) => {
      setSession(updated);
      if (updated.status === "completed") {
        // Missing-field questions are now resolved — completeness score changed.
        void queryClient.invalidateQueries({ queryKey: cvManagementKeys.completeness(documentId) });
      }
    },
  });

  return { session, start, sendMessage };
}
