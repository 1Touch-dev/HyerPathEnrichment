"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Copy, ShieldAlert, Clock, CheckCircle2, RefreshCw } from "lucide-react";
import { JobStatusBadge } from "@/components/console/JobStatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { EnrichmentJob, JobStatus, RequestedTier } from "@/src/lib/types";
import { copyToClipboard, cn } from "@/src/lib/utils";
import { getTierLabel } from "@/src/lib/tier-utils";

type JobProgressProps = {
  job: EnrichmentJob;
  polling?: boolean;
  pollTimedOut?: boolean;
  onRetry?: () => void;
  onRefresh?: () => void;
};

// Estimated time per tier in seconds
const TIER_ESTIMATES: Record<RequestedTier, number> = {
  tier1: 55,
  tier2: 35,
  tier3: 18,
  tier4: 13,
};

function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return "0s";
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs}s`;
}

function statusMessage(status: JobStatus, elapsedSec: number, estimatedRemaining: number | null) {
  switch (status) {
    case "queued":
      return "Waiting in queue…";
    case "running":
      if (estimatedRemaining !== null && estimatedRemaining > 0) {
        return `Processing (est. ${formatTime(estimatedRemaining)} remaining)`;
      }
      return "Pipeline executing…";
    case "completed":
    case "completed_no_data":
      return `Finished in ${formatTime(elapsedSec)}`;
    case "failed":
      return "Job failed";
    case "suppressed":
      return "Identifier opted out — empty dossier";
    default:
      return status;
  }
}

function tierState(tier: RequestedTier, job: EnrichmentJob): "pending" | "active" | "done" {
  if (job.status === "completed" || job.status === "completed_no_data") {
    return "done";
  }
  if (job.status === "queued") {
    return "pending";
  }
  if (job.status === "running") {
    const sources = job.dossier.sources.join(" ").toLowerCase();
    if (sources.includes(tier.replace("tier", "tier ")) || sources.includes(tier)) {
      return "done";
    }
    return "active";
  }
  return "pending";
}

function calculateProgress(job: EnrichmentJob): number {
  if (
    job.status === "completed" ||
    job.status === "completed_no_data" ||
    job.status === "failed" ||
    job.status === "suppressed"
  ) {
    return 100;
  }
  if (job.status === "queued") {
    return 10;
  }
  if (job.status === "running") {
    const requestedTiers = job.input.requestedTiers;
    if (requestedTiers.length === 0) return 50;

    const completedCount = requestedTiers.filter((tier) => tierState(tier, job) === "done").length;

    // Progress from 15% (started) to 95% (almost done)
    const tierProgress = (completedCount / requestedTiers.length) * 80;
    return Math.min(95, 15 + tierProgress);
  }
  return 10;
}

function estimateRemainingTime(job: EnrichmentJob): number | null {
  if (job.status !== "running") return null;

  const requestedTiers = job.input.requestedTiers;
  const pendingTiers = requestedTiers.filter((tier) => tierState(tier, job) !== "done");

  if (pendingTiers.length === 0) return 0;

  return pendingTiers.reduce((sum, tier) => sum + TIER_ESTIMATES[tier], 0);
}

export function JobProgress({ job, polling, pollTimedOut, onRetry, onRefresh }: JobProgressProps) {
  const jobStartTime = useMemo(() => {
    if (!job.createdAt) return Date.now();
    const time = new Date(job.createdAt).getTime();
    return isNaN(time) ? Date.now() : time;
  }, [job.createdAt]);
  const [elapsedSec, setElapsedSec] = useState(() => {
    const elapsed = Math.floor((Date.now() - jobStartTime) / 1000);
    return isNaN(elapsed) ? 0 : Math.max(0, elapsed);
  });
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (
      job.status === "completed" ||
      job.status === "completed_no_data" ||
      job.status === "failed" ||
      job.status === "suppressed"
    ) {
      return;
    }
    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - jobStartTime) / 1000);
      setElapsedSec(isNaN(elapsed) ? 0 : Math.max(0, elapsed));
    }, 1000);
    return () => clearInterval(interval);
  }, [job.status, jobStartTime]);

  const progressValue = useMemo(() => calculateProgress(job), [job]);
  const estimatedRemaining = useMemo(() => estimateRemainingTime(job), [job]);

  const copyId = async () => {
    await copyToClipboard(job.id);
  };

  const handleRefresh = async () => {
    if (!onRefresh || refreshing) return;
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      // Keep spinner for a moment to show feedback
      setTimeout(() => setRefreshing(false), 500);
    }
  };

  return (
    <Card aria-live="polite" aria-atomic="true" role="status">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Job progress</p>
          <CardTitle className="text-lg" id={`job-status-${job.id}`}>
            {statusMessage(job.status, elapsedSec, estimatedRemaining)}
          </CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <code className="rounded bg-muted px-2 py-1 text-xs" aria-label="Job ID">
              {job.id}
            </code>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void copyId()}
              aria-label="Copy job ID to clipboard"
            >
              <Copy className="mr-1 size-3" aria-hidden="true" />
              Copy ID
            </Button>
            <JobStatusBadge status={job.status} />
            {(job.status === "queued" || job.status === "running") && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="size-3" aria-hidden="true" />
                <span aria-label={`Elapsed time: ${formatTime(elapsedSec)}`}>
                  {formatTime(elapsedSec)} elapsed
                </span>
              </div>
            )}
          </div>
        </div>
        {job.status === "failed" && onRetry ? (
          <Button variant="outline" onClick={onRetry} aria-label="Retry failed job">
            Retry
          </Button>
        ) : onRefresh ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleRefresh()}
            disabled={refreshing}
            aria-label="Refresh job status"
          >
            <RefreshCw
              className={cn("mr-1 size-3", refreshing && "animate-spin")}
              aria-hidden="true"
            />
            Refresh
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="space-y-2">
          <Progress
            value={progressValue}
            className={polling ? "animate-pulse" : ""}
            aria-label={`Job progress: ${Math.round(progressValue)} percent complete`}
            aria-valuenow={Math.round(progressValue)}
            aria-valuemin={0}
            aria-valuemax={100}
          />
          <div className="flex justify-between text-xs text-muted-foreground" aria-hidden="true">
            <span>{Math.round(progressValue)}% complete</span>
            {estimatedRemaining !== null && estimatedRemaining > 0 && (
              <span>~{formatTime(estimatedRemaining)} remaining</span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2" role="list" aria-label="Tier progress">
          {job.input.requestedTiers.map((tier) => {
            const state = tierState(tier, job);
            const estimate = TIER_ESTIMATES[tier];
            return (
              <Badge
                key={tier}
                variant={
                  state === "done" ? "success" : state === "active" ? "warning" : "secondary"
                }
                className={cn(state === "active" && "animate-pulse")}
                role="listitem"
                aria-label={`${getTierLabel(tier)}: ${state}, estimated ${estimate} seconds`}
              >
                {state === "done" && <CheckCircle2 className="mr-1 size-3" aria-hidden="true" />}
                {getTierLabel(tier)}
                <span className="ml-1 text-[10px] opacity-70" aria-hidden="true">
                  (~{estimate}s)
                </span>
              </Badge>
            );
          })}
        </div>
        {job.status === "suppressed" ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground" role="alert">
            <ShieldAlert className="size-4" aria-hidden="true" />
            This identifier is on the suppression list. No enrichment data is returned.
          </div>
        ) : null}
        {job.status === "failed" && job.error ? (
          <p className="text-sm text-destructive" role="alert">
            {job.error}
          </p>
        ) : null}
        {pollTimedOut ? (
          <p className="text-sm text-muted-foreground">
            Still running — check{" "}
            <Link href={`/app/jobs/${job.id}`} className="text-primary underline">
              job detail
            </Link>{" "}
            or History.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
