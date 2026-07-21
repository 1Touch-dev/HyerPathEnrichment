import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createEnrichmentJob } from "@/src/lib/api-client";
import { isTerminalStatus } from "@/src/lib/enrich-poll";
import { EnrichmentInput, EnrichMode } from "@/src/lib/types";
import { jobKeys } from "@/features/history";
import { enrichKeys } from "../api/keys";

type CreateJobInput = {
  input: EnrichmentInput;
  mode: EnrichMode;
};

export function useCreateEnrichment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ input, mode }: CreateJobInput) =>
      (await createEnrichmentJob(input, mode)).data,
    onSuccess: (job, { mode }) => {
      if (mode === "sync" || isTerminalStatus(job.status)) {
        queryClient.setQueryData(enrichKeys.job(job.id), job);
      }
      void queryClient.invalidateQueries({ queryKey: enrichKeys.jobs() });
      void queryClient.invalidateQueries({ queryKey: jobKeys.all });
    },
  });
}
