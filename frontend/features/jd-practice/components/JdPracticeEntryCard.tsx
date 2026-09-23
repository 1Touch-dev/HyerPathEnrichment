"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

interface JdPracticeEntryCardProps {
  jobMatchId: string;
}

/**
 * "Practice for this job" entry point (§9.6). Deliberately not gated to any particular
 * `ApplicationStatus` (e.g. "interview") — a candidate may want to practice right after
 * applying, before an interview is even scheduled — so this renders unconditionally
 * wherever the caller places it (e.g. from a tracked-match row or an interview schedule
 * card, wired up by those features separately).
 */
export function JdPracticeEntryCard({ jobMatchId }: JdPracticeEntryCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-[1.25rem] border border-border/70 bg-surface p-4 shadow-panel sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div>
        <p className="font-medium">Practice for this job</p>
        <p className="text-sm text-muted-foreground">
          Get interview questions tailored to this job&apos;s description.
        </p>
      </div>
      <Button asChild size="sm" className="shrink-0 self-start sm:self-auto">
        <Link href={`/app/practice?jobMatchId=${jobMatchId}`}>Start practice</Link>
      </Button>
    </div>
  );
}
