"use client";

import { useState } from "react";
import Link from "next/link";
import { useMatches, useTriggerScan } from "@/features/job-matching";
import { MatchCard } from "@/features/job-matching";
import { EmptyState } from "@/components/console/EmptyState";
import { Button } from "@/components/ui/button";
import { RefreshCw, Settings } from "lucide-react";

export function MatchesView() {
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const { data, isLoading, isError } = useMatches(limit, offset);
  const triggerScan = useTriggerScan();
  // Live unread-count updates are subscribed at the app shell level (see
  // AppShell.tsx) so the nav badge stays fresh on every page, not just this one.

  if (isLoading) {
    return <div className="animate-pulse h-96 rounded-lg bg-muted" />;
  }

  if (isError) {
    return <EmptyState title="Couldn't load matches" description="Please try again shortly." />;
  }

  if (!data || data.matches.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-end">
          <Button asChild variant="ghost" size="icon" aria-label="Match preferences">
            <Link href="/app/matches/settings">
              <Settings className="h-4 w-4" />
            </Link>
          </Button>
        </div>
        <EmptyState
          title="No matches yet"
          description="Upload your CV and set preferences to get started."
          action={
            <Button onClick={() => triggerScan.mutate()} disabled={triggerScan.isPending}>
              <RefreshCw className="mr-2 h-4 w-4" />
              {triggerScan.isPending ? "Scanning..." : "Scan now"}
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Job matches</h1>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => triggerScan.mutate()}
            disabled={triggerScan.isPending}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            {triggerScan.isPending ? "Scanning..." : "Scan now"}
          </Button>
          <Button asChild variant="ghost" size="icon" aria-label="Match preferences">
            <Link href="/app/matches/settings">
              <Settings className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4">
        {data.matches.map((match) => (
          <MatchCard key={match.matchId} match={match} />
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
