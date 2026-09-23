"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Plus } from "lucide-react";
import {
  ShellPageHeader,
  ShellPageHeaderActions,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
  ShellSectionHeader,
  ShellSectionHeaderActions,
  ShellSectionHeaderContent,
  ShellSectionHeaderDescription,
  ShellSectionHeaderTitle,
} from "@/components/layout/ShellPage";
import {
  TrackerFilterBar,
  TrackedMatchRow,
  useTrackedMatches,
} from "@/features/application-tracker";
import { AddManualJobDialog } from "@/features/manual-jobs";
import { EmptyState } from "@/components/console/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

  const matches = data?.matches ?? [];
  const activeCount = matches.filter((match) =>
    ["new", "applied", "replied", "interview"].includes(match.applicationStatus),
  ).length;
  const interviewCount = matches.filter((match) => match.applicationStatus === "interview").length;
  const manualCount = matches.filter((match) => match.overallScore === null).length;

  const header = (
    <ShellPageHeader>
      <ShellPageHeaderContent>
        <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
        <ShellPageHeaderTitle>Applications</ShellPageHeaderTitle>
        <ShellPageHeaderDescription>
          Keep every lead moving with one clean tracker for statuses, interviews, and manually added
          roles.
        </ShellPageHeaderDescription>
      </ShellPageHeaderContent>
      <ShellPageHeaderActions className="items-start sm:items-center">
        <Button variant="outline" size="sm" onClick={() => setAddJobDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          Add a job manually
        </Button>
      </ShellPageHeaderActions>
    </ShellPageHeader>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        {header}
        <div className="grid gap-4 md:grid-cols-3">
          <div className="h-28 animate-pulse rounded-xl border border-border/70 bg-surface shadow-panel" />
          <div className="h-28 animate-pulse rounded-xl border border-border/70 bg-surface shadow-panel" />
          <div className="h-28 animate-pulse rounded-xl border border-border/70 bg-surface shadow-panel" />
        </div>
        <div className="h-96 animate-pulse rounded-xl border border-border/70 bg-surface shadow-panel" />
        {addJobDialog}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
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
        <div className="space-y-6">
          {header}
          <TrackerFilterBar />
          <EmptyState title={`No applications with status '${status}' yet`} />
          {addJobDialog}
        </div>
      );
    }

    return (
      <div className="space-y-6">
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
    <div className="space-y-6">
      {header}
      <div className="grid gap-4 md:grid-cols-3">
        <Card variant="accent">
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Active applications</p>
            <CardTitle className="text-3xl text-primary">{activeCount}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Roles still moving through your funnel.
          </CardContent>
        </Card>
        <Card variant="accent">
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Interviews</p>
            <CardTitle className="text-3xl text-primary">{interviewCount}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Open roles currently in an interview stage.
          </CardContent>
        </Card>
        <Card variant="accent">
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Manual entries</p>
            <CardTitle className="text-3xl text-primary">{manualCount}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Roles you added yourself outside the scan flow.
          </CardContent>
        </Card>
      </div>

      <TrackerFilterBar />

      <ShellSection>
        <ShellSectionHeader>
          <ShellSectionHeaderContent>
            <ShellSectionHeaderTitle>Tracked roles</ShellSectionHeaderTitle>
            <ShellSectionHeaderDescription>
              Keep statuses current so practice, outreach, and interview flows stay in sync.
            </ShellSectionHeaderDescription>
          </ShellSectionHeaderContent>
          <ShellSectionHeaderActions className="text-sm text-muted-foreground">
            Page {offset / limit + 1} of {Math.max(1, Math.ceil(data.total / limit))}
          </ShellSectionHeaderActions>
        </ShellSectionHeader>

        <div className="grid gap-3">
          {data.matches.map((match) => (
            <TrackedMatchRow key={match.matchId} match={match} />
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-4 text-sm text-muted-foreground">
          <span>
            Showing {offset + 1}-{Math.min(offset + limit, data.total)} of {data.total} tracked
            roles
          </span>
          <div className="flex justify-center gap-2">
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
      </ShellSection>
      {addJobDialog}
    </div>
  );
}
