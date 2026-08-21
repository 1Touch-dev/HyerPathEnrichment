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
    <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
      <div>
        <p className="font-medium">Practice for this job</p>
        <p className="text-sm text-muted-foreground">
          Get interview questions tailored to this job&apos;s description.
        </p>
      </div>
      <Button asChild size="sm">
        <Link href={`/app/practice?jobMatchId=${jobMatchId}`}>Start practice</Link>
      </Button>
    </div>
  );
}
