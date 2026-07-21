'use client';

import { useEffect, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { JobHistoryTable } from '@/components/console/JobHistoryTable';
import { evictStaleJobDetails } from '@/features/enrich';
import { useJobListQuery } from '@/features/history';
import { formatApiErrorMessage } from '@/src/lib/format-api-error';

const PAGE_SIZE = 50;

export default function HistoryPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error, isFetching, fetchNextPage, hasNextPage } = useJobListQuery();

  const jobs = useMemo(() => data?.pages.flatMap((page) => page.jobs) ?? [], [data]);
  const total = data?.pages[0]?.total ?? 0;
  const offset = Math.max(0, jobs.length - PAGE_SIZE);

  useEffect(() => {
    evictStaleJobDetails(queryClient, jobs);
  }, [queryClient, jobs]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">History</h1>
        <p className="text-sm text-muted-foreground">Recent enrichment runs with shareable job links.</p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{formatApiErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}

      <JobHistoryTable
        jobs={jobs}
        total={total}
        limit={PAGE_SIZE}
        offset={offset}
        loading={isLoading || isFetching}
        onLoadMore={hasNextPage ? () => void fetchNextPage() : undefined}
      />
    </div>
  );
}
