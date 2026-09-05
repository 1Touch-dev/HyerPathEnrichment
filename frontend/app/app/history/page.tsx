"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { JobHistoryPanel } from "@/components/console/JobHistoryPanel";
import { Button } from "@/components/ui/button";

export default function CandidateHistoryPage() {
  const queryString = useSearchParams().toString();

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">History</h1>
          <p className="text-sm text-muted-foreground">
            Browse Candidate enrichment history and reopen saved dossiers.
          </p>
        </div>
        <Button asChild variant="outline" className="w-fit shrink-0">
          <Link href="/app/dashboard">Back to dashboard</Link>
        </Button>
      </div>

      <JobHistoryPanel jobsBasePath="/app/jobs" queryString={queryString} />
    </div>
  );
}
