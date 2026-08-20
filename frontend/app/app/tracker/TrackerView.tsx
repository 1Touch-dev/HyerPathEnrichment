"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  TrackerFilterBar,
  TrackedMatchRow,
  useTrackedMatches,
} from "@/features/application-tracker";
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
  const limit = 20;

  const { data, isLoading, isError, refetch } = useTrackedMatches(status, sort, limit, offset);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Applications</h1>
        <div className="animate-pulse h-96 rounded-lg bg-muted" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Applications</h1>
        <EmptyState
          title="Couldn't load your applications"
          description="Please try again shortly."
          action={<Button onClick={() => refetch()}>Retry</Button>}
        />
      </div>
    );
  }

  if (!data || data.matches.length === 0) {
    // Distinct from the "no data at all" empty state below — an empty *filtered* view
    // reads very differently to a user than a genuinely empty tracker (§15.5).
    if (status) {
      return (
        <div className="space-y-4">
          <h1 className="text-2xl font-semibold">Applications</h1>
          <TrackerFilterBar />
          <EmptyState title={`No applications with status '${status}' yet`} />
        </div>
      );
    }

    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Applications</h1>
        <EmptyState
          title="No applications tracked yet"
          description="Swipe or browse matches to start tracking."
          action={
            <Button asChild>
              <Link href="/app/matches">Browse matches</Link>
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Applications</h1>
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
    </div>
  );
}
