import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { listEnrichmentJobs } from '@/src/lib/api-client';
import { jobKeys } from '../api/keys';

const PAGE_SIZE = 50;

export function useJobListQuery() {
  return useInfiniteQuery({
    queryKey: jobKeys.all,
    queryFn: ({ pageParam }) => listEnrichmentJobs({ limit: PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _pages, lastOffset) => {
      const nextOffset = lastOffset + lastPage.jobs.length;
      return nextOffset < lastPage.total ? nextOffset : undefined;
    },
  });
}

export function useJobMetricsQuery() {
  return useQuery({
    queryKey: jobKeys.metrics(),
    queryFn: async () => {
      const response = await listEnrichmentJobs({ limit: 100, offset: 0 });
      const jobs = response.jobs;
      const completed = jobs.filter((j) => j.status === 'completed').length;
      const failed = jobs.filter((j) => j.status === 'failed').length;
      const running = jobs.filter((j) => j.status === 'running' || j.status === 'queued').length;
      const successRate = jobs.length ? Math.round((completed / jobs.length) * 100) : 0;
      return {
        total: response.total,
        completed,
        failed,
        running,
        successRate,
        recent: jobs.slice(0, 5),
      };
    },
  });
}
