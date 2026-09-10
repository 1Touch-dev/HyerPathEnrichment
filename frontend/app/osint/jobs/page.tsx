"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { JobHistoryPanel } from "@/components/console/JobHistoryPanel";
import { JobQueuePanel } from "@/components/console/JobQueuePanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  PageHeader,
  PageHeaderActions,
  PageHeaderContent,
  PageHeaderDescription,
  PageHeaderEyebrow,
  PageHeaderTitle,
} from "@/components/ui/page-header";
import { useLocalStorageJobs } from "@/hooks/useLocalStorageJobs";

export default function OsintJobsPage() {
  const searchParams = useSearchParams();
  const queryString = useMemo(() => searchParams.toString(), [searchParams]);
  const lookupHref = queryString ? `/osint?${queryString}` : "/osint";
  const { jobs, activeJobs } = useLocalStorageJobs();
  const reviewableJobs = useMemo(
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

  return (
    <div className="flex flex-col gap-8">
      <PageHeader>
        <PageHeaderContent>
          <PageHeaderEyebrow>OSINT history</PageHeaderEyebrow>
          <PageHeaderTitle>Review active and finished research</PageHeaderTitle>
          <PageHeaderDescription>
            Keep the live queue close, then scan older dossiers and reopen the exact request you
            need without leaving the OSINT shell.
          </PageHeaderDescription>
        </PageHeaderContent>
        <PageHeaderActions className="items-start sm:items-center">
          {searchParams.get("tiers") ? <Badge variant="info">Tier seed retained</Badge> : null}
          <Button asChild variant="outline" className="w-fit shrink-0">
            <Link href={lookupHref}>Back to workbench</Link>
          </Button>
          <Button asChild variant="ghost" className="w-fit shrink-0">
            <Link href="/osint/settings/security">Security</Link>
          </Button>
        </PageHeaderActions>
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-3">
        <JobsMetric
          label="Tracked locally"
          value={jobs.length.toString()}
          description="Queue context stored in this browser for quick follow-up."
        />
        <JobsMetric
          label="Active now"
          value={activeJobs.length.toString()}
          description="Requests still running or waiting to run."
        />
        <JobsMetric
          label="Ready to review"
          value={reviewableJobs.toString()}
          description="Finished, failed, or suppressed jobs available to reopen."
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.82fr)]">
        <div className="min-w-0">
          <JobHistoryPanel jobsBasePath="/osint/jobs" queryString={queryString} />
        </div>
        <div className="flex flex-col gap-6">
          <Card className="overflow-hidden">
            <CardHeader className="gap-4 border-b border-border/60 bg-surface-muted/40">
              <div className="space-y-2">
                <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
                  Review workflow
                </p>
                <CardTitle className="text-xl">Treat jobs as a research trail</CardTitle>
                <CardDescription>
                  Keep the URL tier seed when you bounce back to the workbench, and use the local
                  queue to watch just-created requests settle into dossier-ready states.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3 pt-6">
              <ReviewWorkflowItem
                title="Open the freshest active job first"
                description="The queue stays local so the latest requests remain easy to revisit while they are still running."
              />
              <ReviewWorkflowItem
                title="Use history for durable links"
                description="Older records remain in the server-backed history list even after the local queue ages out."
              />
              <ReviewWorkflowItem
                title="Preserve seeded tiers"
                description="Returning to the workbench keeps the current query string so the intake can reopen with the same tier mix."
              />
            </CardContent>
          </Card>

          <JobQueuePanel jobsBasePath="/osint/jobs" queryString={queryString} />
        </div>
      </div>
    </div>
  );
}

function JobsMetric({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <Card>
      <CardContent className="space-y-2 p-5">
        <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
          {label}
        </p>
        <p className="text-3xl font-semibold tracking-tight text-foreground">{value}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

function ReviewWorkflowItem({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface p-4">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
