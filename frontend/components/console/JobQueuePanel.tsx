"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, ExternalLink, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { JobStatusBadge } from "@/components/console/JobStatusBadge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { formatConsoleTimestamp, formatRelativeTime } from "@/components/console/formatters";
import { useLocalStorageJobs } from "@/hooks/useLocalStorageJobs";

type JobQueuePanelProps = {
  jobsBasePath?: string;
  queryString?: string;
  onJobStatusUpdate?: (jobId: string, status: "completed" | "failed" | "suppressed") => void;
};

export function JobQueuePanel({
  jobsBasePath = "/osint/jobs",
  queryString = "",
  onJobStatusUpdate,
}: JobQueuePanelProps) {
  const { jobs, activeJobs, removeJob, clearCompleted } = useLocalStorageJobs();
  const [isOpen, setIsOpen] = useState(true);
  const completedJobs = useMemo(
    () =>
      jobs.filter(
        (job) =>
          job.status === "completed" || job.status === "failed" || job.status === "suppressed",
      ),
    [jobs],
  );
  const orderedJobs = useMemo(
    () =>
      [...jobs].sort((left, right) => {
        const leftActive = left.status === "queued" || left.status === "running";
        const rightActive = right.status === "queued" || right.status === "running";
        if (leftActive !== rightActive) {
          return leftActive ? -1 : 1;
        }
        return right.createdAt - left.createdAt;
      }),
    [jobs],
  );

  // Notify parent of status changes for completed jobs
  useEffect(() => {
    if (!onJobStatusUpdate) return;

    jobs.forEach((job) => {
      if (job.status === "completed" || job.status === "failed" || job.status === "suppressed") {
        if (job.completedAt && Date.now() - job.completedAt < 1000) {
          onJobStatusUpdate(job.id, job.status);
        }
      }
    });
  }, [jobs, onJobStatusUpdate]);

  if (jobs.length === 0) {
    return null;
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="overflow-hidden">
        <CardHeader className="gap-4 border-b border-border/60 bg-surface-muted/40 pb-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
                Live queue
              </p>
              <div className="space-y-1">
                <CardTitle className="text-lg">
                  Active work
                  {activeJobs.length > 0 ? (
                    <span className="ml-2 align-middle text-base text-muted-foreground">
                      {activeJobs.length} running
                    </span>
                  ) : null}
                </CardTitle>
                <CardDescription>
                  Recent requests stay here while they are in progress, then linger briefly for
                  quick follow-up.
                </CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">{jobs.length} tracked</Badge>
                <Badge variant={activeJobs.length > 0 ? "warning" : "secondary"}>
                  {activeJobs.length} active
                </Badge>
                {completedJobs.length > 0 ? (
                  <Badge variant="success">{completedJobs.length} ready to review</Badge>
                ) : null}
              </div>
            </div>

            <div className="flex items-center gap-2 self-start">
              {completedJobs.length > 0 && (
                <Button variant="ghost" size="sm" onClick={clearCompleted} className="text-xs">
                  Clear completed
                </Button>
              )}
              <CollapsibleTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={isOpen ? "Collapse queue" : "Expand queue"}
                >
                  {isOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                </Button>
              </CollapsibleTrigger>
            </div>
          </div>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="pt-5">
            <div className="space-y-3">
              {orderedJobs.map((job) => (
                <div
                  key={job.id}
                  className="flex flex-col gap-3 rounded-xl border border-border/70 bg-surface p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <JobStatusBadge status={job.status} />
                      <span className="text-sm font-medium text-foreground">
                        {job.status === "queued" || job.status === "running"
                          ? "Request in progress"
                          : "Recent request"}
                      </span>
                    </div>
                    <code className="mt-2 block truncate rounded-md bg-muted px-2.5 py-1.5 text-xs text-muted-foreground">
                      {job.id}
                    </code>
                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>Started {formatRelativeTime(job.createdAt)}</span>
                      <span>{formatConsoleTimestamp(job.createdAt)}</span>
                      {job.completedAt ? (
                        <span>Finished {formatRelativeTime(job.completedAt)}</span>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 self-start sm:self-center">
                    <Button variant="outline" size="sm" asChild>
                      <Link
                        href={`${jobsBasePath}/${job.id}${queryString ? `?${queryString}` : ""}`}
                        aria-label={`Open job ${job.id}`}
                      >
                        <ExternalLink className="mr-1 size-3" />
                        Open
                      </Link>
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => removeJob(job.id)}>
                      <X className="mr-1 size-3" />
                      Remove
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
