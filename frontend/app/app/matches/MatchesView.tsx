"use client";

import { useState } from "react";
import { useMatches, useTriggerScan, useUnreadMatchEvents } from "@/features/job-matching";
import { MatchCard } from "@/features/job-matching";
import { EmptyState } from "@/components/console/EmptyState";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";

export function MatchesView() {
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const { data, isLoading, isError } = useMatches(limit, offset);
  const triggerScan = useTriggerScan();
  // Subscribed here (rather than in a layout) since this is currently the only
  // view that needs live updates — simplest placement that still covers the
  // "subscribe while mounted" requirement.
  useUnreadMatchEvents();

  if (isLoading) {
    return <div className="animate-pulse h-96 rounded-lg bg-muted" />;
  }

  if (isError) {
    return <EmptyState title="Couldn't load matches" description="Please try again shortly." />;
  }

  if (!data || data.matches.length === 0) {
    return (
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
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Job matches</h1>
        <Button
          variant="outline"
          onClick={() => triggerScan.mutate()}
          disabled={triggerScan.isPending}
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          {triggerScan.isPending ? "Scanning..." : "Scan now"}
        </Button>
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
