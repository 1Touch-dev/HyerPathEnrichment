import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createEnrichmentJob } from '@/src/lib/api-client';
import { EnrichmentInput, EnrichMode } from '@/src/lib/types';
import { enrichKeys } from '../api/keys';

type CreateJobInput = {
  input: EnrichmentInput;
  mode: EnrichMode;
};

export function useCreateEnrichment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ input, mode }: CreateJobInput) => createEnrichmentJob(input, mode),
    onSuccess: (job) => {
      queryClient.setQueryData(enrichKeys.job(job.id), job);
      void queryClient.invalidateQueries({ queryKey: enrichKeys.jobs() });
    },
  });
}
