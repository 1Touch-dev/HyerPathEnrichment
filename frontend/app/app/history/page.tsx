"use client";

import { useEffect, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { JobHistoryTable } from "@/components/console/JobHistoryTable";
import { evictStaleJobDetails } from "@/features/enrich";
import { useJobListQuery } from "@/features/history";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { useInterval } from "@/hooks/useInterval";
import { jobKeys } from "@/features/history";

const PAGE_SIZE = 50;
const POLL_INTERVAL_MS = 5000; // 5 seconds

export default function HistoryPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error, isFetching, fetchNextPage, hasNextPage, refetch } =
    useJobListQuery();

  const jobs = useMemo(() => data?.pages.flatMap((page) => page.jobs) ?? [], [data]);
  const total = data?.pages[0]?.total ?? 0;
  const offset = Math.max(0, jobs.length - PAGE_SIZE);

  // Check if any jobs are in progress
  const hasActiveJobs = useMemo(
    () => jobs.some((job) => job.status === "queued" || job.status === "running"),
    [jobs],
  );

  useEffect(() => {
    evictStaleJobDetails(queryClient, jobs);
  }, [queryClient, jobs]);

  // Poll for updates when there are active jobs
  useInterval(
    () => {
      void refetch();
    },
    hasActiveJobs && !isLoading ? POLL_INTERVAL_MS : null,
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            History
            {isFetching && !isLoading && (
              <Loader2 className="ml-2 inline size-4 animate-spin text-muted-foreground" />
            )}
          </h1>
          <p className="text-sm text-muted-foreground">
            Recent enrichment runs with shareable job links.
            {hasActiveJobs && " Auto-refreshing for active jobs."}
          </p>
        </div>
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
