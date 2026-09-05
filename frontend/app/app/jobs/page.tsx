"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { JobHistoryPanel } from "@/components/console/JobHistoryPanel";
import { JobQueuePanel } from "@/components/console/JobQueuePanel";
import { Button } from "@/components/ui/button";

export default function CandidateJobsPage() {
  const queryString = useSearchParams().toString();

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
          <p className="text-sm text-muted-foreground">
            Monitor queued work, browse enrichment history, and open dossiers.
          </p>
        </div>
        <Button asChild variant="outline" className="w-fit shrink-0">
          <Link href="/app/dashboard">Back to dashboard</Link>
        </Button>
      </div>

      <JobQueuePanel jobsBasePath="/app/jobs" queryString={queryString} />
      <JobHistoryPanel jobsBasePath="/app/jobs" queryString={queryString} />
    </div>
  );
}
