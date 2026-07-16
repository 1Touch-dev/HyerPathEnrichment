'use client';

import { useParams } from 'next/navigation';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { DossierView } from '@/components/console/DossierView';
import { JobProgress } from '@/components/console/JobProgress';
import { EmptyState } from '@/components/console/EmptyState';
import { useJobQuery } from '@/features/enrich';
import { isTerminalStatus } from '@/src/lib/enrich-poll';

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const { data: job, isLoading, error, isFetching } = useJobQuery(jobId);

  if (isLoading && !job) {
    return <EmptyState title="Loading job…" description={`Fetching ${jobId}`} />;
  }

  if (error && !job) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>
    );
  }

  if (!job) {
    return <EmptyState title="Job not found" description={`No job with id ${jobId}`} />;
  }

  const polling = isFetching && !isTerminalStatus(job.status);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Job dossier</h1>
        <p className="font-mono text-sm text-muted-foreground">{job.id}</p>
      </div>
      <JobProgress job={job} polling={polling} pollTimedOut={false} />
      <DossierView job={job} />
    </div>
  );
}
