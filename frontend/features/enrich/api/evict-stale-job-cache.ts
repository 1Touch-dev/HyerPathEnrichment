import type { QueryClient } from '@tanstack/react-query';
import { isTerminalStatus } from '@/src/lib/enrich-poll';
import type { EnrichmentJob, JobListItem } from '@/src/lib/types';
import { enrichKeys } from './keys';

/** Drop job-detail cache when the list says terminal but detail is still in-flight. */
export function evictStaleJobDetails(queryClient: QueryClient, jobs: JobListItem[]): void {
  for (const item of jobs) {
    if (!isTerminalStatus(item.status)) {
      continue;
    }
    const cached = queryClient.getQueryData<EnrichmentJob>(enrichKeys.job(item.id));
    if (cached && !isTerminalStatus(cached.status)) {
      queryClient.removeQueries({ queryKey: enrichKeys.job(item.id) });
    }
  }
}
