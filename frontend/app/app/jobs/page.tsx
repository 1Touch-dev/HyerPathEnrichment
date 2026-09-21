"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { JobHistoryPanel } from "@/components/console/JobHistoryPanel";
import { JobQueuePanel } from "@/components/console/JobQueuePanel";
import {
  ShellPageHeader,
  ShellPageHeaderActions,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
  ShellSectionHeader,
  ShellSectionHeaderContent,
  ShellSectionHeaderDescription,
  ShellSectionHeaderTitle,
} from "@/components/layout/ShellPage";
import { Button } from "@/components/ui/button";

export default function CandidateJobsPage() {
  const queryString = useSearchParams().toString();

  return (
    <div className="flex flex-col gap-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>Jobs</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Monitor queued work, browse enrichment history, and open dossiers.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
        <ShellPageHeaderActions>
          <Button asChild variant="outline" className="w-fit shrink-0">
            <Link href="/app/dashboard">Back to dashboard</Link>
          </Button>
        </ShellPageHeaderActions>
      </ShellPageHeader>

      <ShellSection surface="muted">
        <ShellSectionHeader>
          <ShellSectionHeaderContent>
            <ShellSectionHeaderTitle>Queue</ShellSectionHeaderTitle>
            <ShellSectionHeaderDescription>
              Shared workflow surfaces stay intact; this page only reframes them for the candidate
              shell.
            </ShellSectionHeaderDescription>
          </ShellSectionHeaderContent>
        </ShellSectionHeader>
        <JobQueuePanel jobsBasePath="/app/jobs" queryString={queryString} />
      </ShellSection>

      <ShellSection>
        <ShellSectionHeader>
          <ShellSectionHeaderContent>
            <ShellSectionHeaderTitle>History</ShellSectionHeaderTitle>
            <ShellSectionHeaderDescription>
              Reopen completed work and follow the same query-preserving links into dossier detail.
            </ShellSectionHeaderDescription>
          </ShellSectionHeaderContent>
        </ShellSectionHeader>
        <JobHistoryPanel jobsBasePath="/app/jobs" queryString={queryString} />
      </ShellSection>
    </div>
  );
}
