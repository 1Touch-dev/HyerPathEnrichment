"use client";

import { useEffect, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { JobHistoryTable } from "@/components/console/JobHistoryTable";
import {
  SectionHeader,
  SectionHeaderActions,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderEyebrow,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
import { evictStaleJobDetails } from "@/features/enrich";
import { useJobListQuery } from "@/features/history";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { useInterval } from "@/hooks/useInterval";

const PAGE_SIZE = 50;
const POLL_INTERVAL_MS = 5000;

type JobHistoryPanelProps = {
  jobsBasePath?: string;
  queryString?: string;
};

export function JobHistoryPanel({
  jobsBasePath = "/osint/jobs",
  queryString = "",
}: JobHistoryPanelProps = {}) {
  const queryClient = useQueryClient();
  const { data, isLoading, error, isFetching, fetchNextPage, hasNextPage, refetch } =
    useJobListQuery();

  const jobs = useMemo(() => data?.pages.flatMap((page) => page.jobs) ?? [], [data]);
  const total = data?.pages[0]?.total ?? 0;
  const hasActiveJobs = useMemo(
    () => jobs.some((job) => job.status === "queued" || job.status === "running"),
    [jobs],
  );
  const completedJobs = useMemo(
    () =>
      jobs.filter(
        (job) =>
          job.status === "completed" ||
          job.status === "completed_no_data" ||
          job.status === "failed" ||
          job.status === "suppressed",
      ).length,
    [jobs],
  );

  useEffect(() => {
    evictStaleJobDetails(queryClient, jobs);
  }, [queryClient, jobs]);

  useInterval(
    () => {
      void refetch();
    },
    hasActiveJobs && !isLoading ? POLL_INTERVAL_MS : null,
  );

  return (
    <section
      className="flex flex-col overflow-hidden rounded-xl border border-border/70 bg-card shadow-sm"
      aria-labelledby="job-history-heading"
      aria-busy={isFetching}
    >
      <div className="border-b border-border/60 bg-primary-soft/40 px-4 py-5 sm:px-6">
        <SectionHeader>
          <SectionHeaderContent>
            <SectionHeaderEyebrow className="text-primary">History</SectionHeaderEyebrow>
            <SectionHeaderTitle id="job-history-heading">Recent requests</SectionHeaderTitle>
            <SectionHeaderDescription>
              Browse finished dossiers, reopen active work, and keep a stable link to each request.
            </SectionHeaderDescription>
          </SectionHeaderContent>
          <SectionHeaderActions className="gap-2">
            <Badge variant="info">{total} total</Badge>
            <Badge variant={hasActiveJobs ? "warning" : "secondary"}>
              {hasActiveJobs ? "Live updates on" : "No active jobs"}
            </Badge>
            <Badge variant="success">{completedJobs} reviewable</Badge>
            {isFetching && !isLoading ? (
              <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                Refreshing
              </span>
            ) : null}
          </SectionHeaderActions>
        </SectionHeader>
      </div>

      <div className="flex flex-col gap-6 p-4 sm:p-6">
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{formatApiErrorMessage(error)}</AlertDescription>
          </Alert>
        ) : null}

        <JobHistoryTable
          jobs={jobs}
          total={total}
          limit={PAGE_SIZE}
          jobsBasePath={jobsBasePath}
          queryString={queryString}
          loading={isLoading}
          refreshing={isFetching && !isLoading}
          onLoadMore={hasNextPage ? () => void fetchNextPage() : undefined}
        />
      </div>
    </section>
  );
}
