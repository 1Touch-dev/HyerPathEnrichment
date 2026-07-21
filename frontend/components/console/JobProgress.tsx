"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Copy, ShieldAlert } from "lucide-react";
import { JobStatusBadge } from "@/components/console/JobStatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { EnrichmentJob, JobStatus, RequestedTier } from "@/src/lib/types";
import { copyToClipboard } from "@/src/lib/utils";
import { getTierLabel } from "@/src/lib/tier-utils";

type JobProgressProps = {
  job: EnrichmentJob;
  polling?: boolean;
  pollTimedOut?: boolean;
  onRetry?: () => void;
};

function statusMessage(status: JobStatus, elapsedSec: number) {
  switch (status) {
    case "queued":
      return "Waiting in queue…";
    case "running":
      return "Pipeline executing…";
    case "completed":
      return `Finished in ${elapsedSec}s`;
    case "failed":
      return "Job failed";
    case "suppressed":
      return "Identifier opted out — empty dossier";
    default:
      return status;
  }
}

function tierState(tier: RequestedTier, job: EnrichmentJob): "pending" | "active" | "done" {
  if (job.status === "completed") {
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

export function JobProgress({ job, polling, pollTimedOut, onRetry }: JobProgressProps) {
  const [startedAt] = useState(() => Date.now());
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    if (job.status === "completed" || job.status === "failed" || job.status === "suppressed") {
      return;
    }
    const interval = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [job.status, startedAt]);

  const progressValue = useMemo(() => {
    if (job.status === "completed" || job.status === "failed" || job.status === "suppressed") {
      return 100;
    }
    if (job.status === "running") {
      return 66;
    }
    if (job.status === "queued") {
      return 20;
    }
    return 10;
  }, [job.status]);

  const copyId = async () => {
    await copyToClipboard(job.id);
  };

  return (
    <Card aria-live="polite">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Job progress</p>
          <CardTitle className="text-lg">{statusMessage(job.status, elapsedSec)}</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <code className="rounded bg-muted px-2 py-1 text-xs">{job.id}</code>
            <Button variant="outline" size="sm" onClick={() => void copyId()}>
              <Copy className="mr-1 size-3" />
              Copy ID
            </Button>
            <JobStatusBadge status={job.status} />
          </div>
        </div>
        {job.status === "failed" && onRetry ? (
          <Button variant="outline" onClick={onRetry}>
            Retry
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Progress value={progressValue} className={polling ? "animate-pulse" : ""} />
        <div className="flex flex-wrap gap-2">
          {job.input.requestedTiers.map((tier) => {
            const state = tierState(tier, job);
            return (
              <Badge
                key={tier}
                variant={
                  state === "done" ? "success" : state === "active" ? "warning" : "secondary"
                }
              >
                {getTierLabel(tier)} · {state}
              </Badge>
            );
          })}
        </div>
        {job.status === "suppressed" ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldAlert className="size-4" />
            This identifier is on the suppression list. No enrichment data is returned.
          </div>
        ) : null}
        {job.status === "failed" && job.error ? (
          <p className="text-sm text-destructive">{job.error}</p>
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
