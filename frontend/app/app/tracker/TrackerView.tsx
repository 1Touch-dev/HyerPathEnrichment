"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Plus } from "lucide-react";
import {
  TrackerFilterBar,
  TrackedMatchRow,
  useTrackedMatches,
} from "@/features/application-tracker";
import { AddManualJobDialog } from "@/features/manual-jobs";
import { EmptyState } from "@/components/console/EmptyState";
import { Button } from "@/components/ui/button";
import type { ApplicationStatus } from "@/src/lib/types";

const VALID_STATUSES: ApplicationStatus[] = [
  "new",
  "applied",
  "replied",
  "interview",
  "offer",
  "rejected",
];

function parseStatus(value: string | null): ApplicationStatus | undefined {
  return VALID_STATUSES.includes(value as ApplicationStatus)
    ? (value as ApplicationStatus)
    : undefined;
}

export function TrackerView() {
  const searchParams = useSearchParams();
  const status = parseStatus(searchParams.get("status"));
  const sort = searchParams.get("sort") ?? "newest";

  const [offset, setOffset] = useState(0);
  const [addJobDialogOpen, setAddJobDialogOpen] = useState(false);
  const limit = 20;

  const { data, isLoading, isError, refetch } = useTrackedMatches(status, sort, limit, offset);

  // Rendered once and reused across every loading/error/empty/success branch below, so
  // "Add a job manually" is always reachable — a candidate with a broken/empty tracker
  // load shouldn't lose the ability to add a job while that's being sorted out.
  const addJobDialog = (
    <AddManualJobDialog open={addJobDialogOpen} onOpenChange={setAddJobDialogOpen} />
  );

  const header = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-semibold">Applications</h1>
      <Button variant="outline" size="sm" onClick={() => setAddJobDialogOpen(true)}>
        <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
        Add a job manually
      </Button>
    </div>
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        {header}
        <div className="animate-pulse h-96 rounded-lg bg-muted" />
        {addJobDialog}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-4">
        {header}
        <EmptyState
          title="Couldn't load your applications"
          description="Please try again shortly."
          action={<Button onClick={() => refetch()}>Retry</Button>}
        />
        {addJobDialog}
      </div>
    );
  }

  if (!data || data.matches.length === 0) {
    // Distinct from the "no data at all" empty state below — an empty *filtered* view
    // reads very differently to a user than a genuinely empty tracker (§15.5).
    if (status) {
      return (
        <div className="space-y-4">
          {header}
          <TrackerFilterBar />
          <EmptyState title={`No applications with status '${status}' yet`} />
          {addJobDialog}
        </div>
      );
    }

    return (
      <div className="space-y-4">
        {header}
        <EmptyState
          title="No applications tracked yet"
          description="Swipe or browse matches to start tracking."
          action={
            <Button asChild>
              <Link href="/app/matches">Browse matches</Link>
            </Button>
          }
        />
        {addJobDialog}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {header}
      <TrackerFilterBar />

      <div className="grid gap-3">
        {data.matches.map((match) => (
          <TrackedMatchRow key={match.matchId} match={match} />
        ))}
      </div>

      <div className="flex justify-center gap-2 pt-4">
        <Button
          variant="ghost"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - limit))}
        >
          Previous
        </Button>
        <Button
          variant="ghost"
          disabled={offset + limit >= data.total}
          onClick={() => setOffset(offset + limit)}
        >
          Next
        </Button>
      </div>
      {addJobDialog}
    </div>
  );
}
