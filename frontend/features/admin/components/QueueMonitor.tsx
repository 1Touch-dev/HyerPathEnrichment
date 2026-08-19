"use client";

import { useState } from "react";
import { Fragment } from "react";
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useFailedJobs, useQueuesOverview, useRetryFailedJob } from "../hooks/useQueues";
import type { QueueSnapshot } from "@/src/lib/types";

function formatAge(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

function FailedJobList({ queueName }: { queueName: string }) {
  const { data: failedJobs, isLoading } = useFailedJobs(queueName);
  const retryJob = useRetryFailedJob(queueName);

  if (isLoading) return <p className="p-4 text-sm text-muted-foreground">Loading failed jobs…</p>;
  if (!failedJobs?.length) {
    return <p className="p-4 text-sm text-muted-foreground">No failed jobs in this queue.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Job ID</TableHead>
          <TableHead>Function</TableHead>
          <TableHead>Failed at</TableHead>
          <TableHead>Error</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {failedJobs.map((job) => (
          <TableRow key={job.jobId}>
            <TableCell className="font-mono text-xs">{job.jobId}</TableCell>
            <TableCell className="text-sm">{job.funcName ?? "—"}</TableCell>
            <TableCell className="text-xs text-muted-foreground">{job.failedAt ?? "—"}</TableCell>
            <TableCell className="max-w-[280px] truncate text-xs text-muted-foreground">
              {job.excInfo ?? "—"}
            </TableCell>
            <TableCell>
              <Button
                variant="outline"
                size="sm"
                disabled={retryJob.isPending}
                onClick={() => retryJob.mutate(job.jobId)}
              >
                <RefreshCw className="mr-1 size-3" />
                Retry
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/**
 * One row per queue: queued/failed count, oldest-job age, and worker count —
 * this repo's four relevant signals for a *queue* (adapted from the
 * "four panels on a shared time axis" per-service principle in
 * docs/admin-module-research.md §2, applied at queue granularity, §12.4).
 */
export function QueueMonitor() {
  const { data: queues, isLoading } = useQueuesOverview();
  const [expandedQueue, setExpandedQueue] = useState<string | null>(null);

  if (!queues?.length && !isLoading) {
    return <EmptyState title="No queues configured" description="No RQ queues were found." />;
  }

  function toggleExpanded(queue: QueueSnapshot) {
    setExpandedQueue((current) => (current === queue.name ? null : queue.name));
  }

  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Queue</TableHead>
            <TableHead>Priority</TableHead>
            <TableHead>Queued</TableHead>
            <TableHead>Failed</TableHead>
            <TableHead>Oldest job age</TableHead>
            <TableHead>Workers</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(queues ?? []).map((queue) => (
            <Fragment key={queue.name}>
              <TableRow>
                <TableCell className="font-medium">{queue.name}</TableCell>
                <TableCell>{queue.priority}</TableCell>
                <TableCell>{queue.queuedCount}</TableCell>
                <TableCell>
                  <button
                    type="button"
                    onClick={() => toggleExpanded(queue)}
                    className="flex items-center gap-1 text-left"
                    disabled={queue.failedCount === 0}
                  >
                    {queue.failedCount > 0 ? (
                      expandedQueue === queue.name ? (
                        <ChevronDown className="size-3" />
                      ) : (
                        <ChevronRight className="size-3" />
                      )
                    ) : null}
                    <Badge variant={queue.failedCount > 0 ? "destructive" : "outline"}>
                      {queue.failedCount}
                    </Badge>
                  </button>
                </TableCell>
                <TableCell>{formatAge(queue.oldestQueuedAgeSeconds)}</TableCell>
                <TableCell>{queue.workersListening}</TableCell>
              </TableRow>
              {expandedQueue === queue.name ? (
                <TableRow>
                  <TableCell colSpan={6} className="bg-muted/30 p-0">
                    <FailedJobList queueName={queue.name} />
                  </TableCell>
                </TableRow>
              ) : null}
            </Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
