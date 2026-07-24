"use client";

import { useParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DossierView } from "@/components/console/DossierView";
import { JobProgress } from "@/components/console/JobProgress";
import { EmptyState } from "@/components/console/EmptyState";
import { useJobQuery } from "@/features/enrich";
import { EnrichmentJob } from "@/src/lib/types";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { isTerminalStatus } from "@/src/lib/enrich-poll";

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-2 h-4 w-96" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
          <Skeleton className="mt-2 h-4 w-64" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-2 w-full" />
          <div className="flex gap-2">
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-6 w-20" />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </CardContent>
      </Card>
    </div>
  );
}

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const { data: job, isLoading, error, isFetching, isPending } = useJobQuery(jobId);

  // Show loading skeleton only on initial load with no data
  if ((isLoading || isPending) && !job) {
    return <LoadingSkeleton />;
  }

  // Show error if request failed and we have no job data
  if (error && !job) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{formatApiErrorMessage(error)}</AlertDescription>
      </Alert>
    );
  }

  if (!job) {
    return <EmptyState title="Job not found" description={`No job with id ${jobId}`} />;
  }

  const isPolling = isFetching && !isTerminalStatus(job.status);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Job dossier</h1>
          <p className="font-mono text-sm text-muted-foreground">{job.id}</p>
        </div>
        {isPolling && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            <span>Checking for updates...</span>
          </div>
        )}
      </div>
      <JobProgress job={job} polling={isPolling} pollTimedOut={false} />
      <DossierView job={job} />
    </div>
  );
}
