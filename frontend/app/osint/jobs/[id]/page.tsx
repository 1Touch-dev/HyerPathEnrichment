"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DossierView } from "@/components/console/DossierView";
import { EmptyState } from "@/components/console/EmptyState";
import { JobProgress } from "@/components/console/JobProgress";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobQuery } from "@/features/enrich";
import { isTerminalStatus } from "@/src/lib/enrich-poll";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";

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

export default function OsintJobDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const jobId = params.id;
  const { data: job, isLoading, error, isFetching, isPending, refetch } = useJobQuery(jobId);

  const lastStatusRef = useRef(job?.status);
  const lastStatusChangeRef = useRef(Date.now());

  useEffect(() => {
    if (job?.dossier) {
      console.log("[DEBUG] Job dossier data:", {
        jobId: job.id,
        status: job.status,
        dossier: job.dossier,
        hasPhoto: !!job.dossier.photo,
        photoUrl: job.dossier.photo?.assetUrl,
        handleCount: job.dossier.handles?.length || 0,
        emailCount: job.dossier.emails?.length || 0,
        sourceCount: job.dossier.sources?.length || 0,
      });
    }
  }, [job]);

  useEffect(() => {
    if (!job) return;

    if (job.status !== lastStatusRef.current) {
      lastStatusRef.current = job.status;
      lastStatusChangeRef.current = Date.now();
    }

    if (isTerminalStatus(job.status)) return;

    const checkInterval = setInterval(() => {
      const timeSinceChange = Date.now() - lastStatusChangeRef.current;
      if (timeSinceChange > 30000) {
        console.log("Stuck state detected, triggering refetch");
        void refetch();
      }
    }, 10000);

    return () => clearInterval(checkInterval);
  }, [job, refetch]);

  if ((isLoading || isPending) && !job) {
    return <LoadingSkeleton />;
  }

  if (error && !job) {
    const isNotFound = error.message?.includes("404") || error.message?.includes("not found");

    return (
      <div className="flex flex-col gap-4">
        <Button variant="ghost" onClick={() => router.push("/osint/jobs")} className="w-fit">
          <ArrowLeft className="mr-2 size-4" />
          Back to Jobs
        </Button>
        <Alert variant="destructive">
          <AlertDescription>
            {isNotFound
              ? `Job ${jobId} not found. It may have been deleted or expired.`
              : formatApiErrorMessage(error)}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex flex-col gap-4">
        <Button variant="ghost" onClick={() => router.push("/osint/jobs")} className="w-fit">
          <ArrowLeft className="mr-2 size-4" />
          Back to Jobs
        </Button>
        <EmptyState title="Job not found" description={`No job with id ${jobId}`} />
      </div>
    );
  }

  const isPolling = isFetching && !isTerminalStatus(job.status);

  return (
    <div className="flex flex-col gap-6">
      <Button variant="ghost" onClick={() => router.push("/osint/jobs")} className="w-fit">
        <ArrowLeft className="mr-2 size-4" />
        Back to Jobs
      </Button>
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
      <JobProgress job={job} polling={isPolling} pollTimedOut={false} onRefresh={() => refetch()} />
      <DossierView job={job} />
    </div>
  );
}
