"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { JobHistoryPanel } from "@/components/console/JobHistoryPanel";
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

export default function CandidateHistoryPage() {
  const queryString = useSearchParams().toString();

  return (
    <div className="flex flex-col gap-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>History</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Browse Candidate enrichment history and reopen saved dossiers.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
        <ShellPageHeaderActions>
          <Button asChild variant="outline" className="w-fit shrink-0">
            <Link href="/app/dashboard">Back to dashboard</Link>
          </Button>
        </ShellPageHeaderActions>
      </ShellPageHeader>

      <ShellSection>
        <ShellSectionHeader>
          <ShellSectionHeaderContent>
            <ShellSectionHeaderTitle>Past work</ShellSectionHeaderTitle>
            <ShellSectionHeaderDescription>
              This route keeps the shared history internals untouched while giving the candidate
              shell a calmer, more guided frame.
            </ShellSectionHeaderDescription>
          </ShellSectionHeaderContent>
        </ShellSectionHeader>
        <JobHistoryPanel jobsBasePath="/app/jobs" queryString={queryString} />
      </ShellSection>
    </div>
  );
}
