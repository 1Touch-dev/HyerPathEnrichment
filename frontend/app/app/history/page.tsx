'use client';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { JobHistoryTable } from '@/components/console/JobHistoryTable';
import { useJobListQuery } from '@/features/history';

const PAGE_SIZE = 50;

export default function HistoryPage() {
  const { data, isLoading, error, isFetching, fetchNextPage, hasNextPage } = useJobListQuery();

  const jobs = data?.pages.flatMap((page) => page.jobs) ?? [];
  const total = data?.pages[0]?.total ?? 0;
  const offset = Math.max(0, jobs.length - PAGE_SIZE);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Job history</h1>
        <p className="text-sm text-muted-foreground">Paginated enrichment runs with shareable job links.</p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error.message}</AlertDescription>
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
