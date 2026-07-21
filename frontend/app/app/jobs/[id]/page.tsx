"use client";

import { useParams } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { DossierView } from "@/components/console/DossierView";
import { JobProgress } from "@/components/console/JobProgress";
import { EmptyState } from "@/components/console/EmptyState";
import { isJobPendingError, useJobQuery } from "@/features/enrich";
import { EnrichmentJob } from "@/src/lib/types";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";

function pendingJobStub(jobId: string): EnrichmentJob {
  return {
    id: jobId,
    status: "queued",
    input: { requestedTiers: [] },
    dossier: {
      handles: [],
      emails: [],
      verifiedEmails: [],
      coworkers: [],
      jobs: [],
      confidence: [],
      sources: [],
      metadata: {
        generatedAt: "",
        pipelineId: "",
        requestedTiers: [],
        identifierSummary: "",
      },
    },
  };
}

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const { data: job, isLoading, error, isFetching, isPending, failureReason } = useJobQuery(jobId);

  const pending =
    Boolean(jobId) &&
    !job &&
    (isJobPendingError(error) || isJobPendingError(failureReason) || isPending || isFetching);

  if (pending && jobId) {
    const stub = pendingJobStub(jobId);
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Job dossier</h1>
          <p className="font-mono text-sm text-muted-foreground">{jobId}</p>
        </div>
        <JobProgress job={stub} polling={isFetching || isPending} pollTimedOut={false} />
        <DossierView job={stub} />
      </div>
    );
  }

  if (isLoading && !job) {
    return <EmptyState title="Loading job…" description={`Fetching ${jobId}`} />;
  }

  if (error && !job && !isJobPendingError(error)) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{formatApiErrorMessage(error)}</AlertDescription>
      </Alert>
    );
  }

  if (!job) {
    return <EmptyState title="Job not found" description={`No job with id ${jobId}`} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Job dossier</h1>
        <p className="font-mono text-sm text-muted-foreground">{job.id}</p>
      </div>
      <JobProgress job={job} polling={false} pollTimedOut={false} />
      <DossierView job={job} />
    </div>
  );
}
