"use client";

import { useState } from "react";
import Link from "next/link";
import { useMatches, useTriggerScan } from "@/features/job-matching";
import { MatchCard } from "@/features/job-matching";
import { EmptyState } from "@/components/console/EmptyState";
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
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Settings, Sparkles, Target, TrendingUp } from "lucide-react";

export function MatchesView() {
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const { data, isLoading, isError } = useMatches(limit, offset);
  const triggerScan = useTriggerScan();
  // Live unread-count updates are subscribed at the app shell level (see
  // AppShell.tsx) so the nav badge stays fresh on every page, not just this one.
  const matches = data?.matches ?? [];
  const newMatches = matches.filter((match) => match.isNew).length;
  const highFitMatches = matches.filter(
    (match) => match.scoreBreakdown.below_similarity_threshold !== true && match.overallScore >= 80,
  ).length;
  const appliedMatches = matches.filter((match) => match.appliedAt !== null).length;

  const header = (
    <ShellPageHeader>
      <ShellPageHeaderContent>
        <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
        <ShellPageHeaderTitle>Job matches</ShellPageHeaderTitle>
        <ShellPageHeaderDescription>
          Review the latest roles, give quick feedback, and jump into apply, swipe, or outreach
          flows without leaving your candidate lane.
        </ShellPageHeaderDescription>
      </ShellPageHeaderContent>
      <ShellPageHeaderActions className="items-start sm:items-center">
        <Button asChild variant="outline">
          <Link href="/app/matches/swipe">Try swipe view</Link>
        </Button>
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
      </ShellPageHeaderActions>
    </ShellPageHeader>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        {header}
        <div className="grid gap-4 md:grid-cols-3">
          <div className="animate-pulse rounded-lg bg-muted h-28" />
          <div className="animate-pulse rounded-lg bg-muted h-28" />
          <div className="animate-pulse rounded-lg bg-muted h-28" />
        </div>
        <div className="animate-pulse h-96 rounded-lg bg-muted" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        {header}
        <EmptyState title="Couldn't load matches" description="Please try again shortly." />
      </div>
    );
  }

  if (!data || matches.length === 0) {
    return (
      <div className="space-y-6">
        {header}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Sparkles className="h-4 w-4 text-primary" />
                First step
              </div>
              <CardTitle className="text-xl">Upload your CV</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Documents power scans, preferences, and practice personalization.
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Target className="h-4 w-4 text-primary" />
                Then refine
              </div>
              <CardTitle className="text-xl">Set your preferences</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Choose roles, locations, salary, and notification channels.
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <TrendingUp className="h-4 w-4 text-primary" />
                Finally scan
              </div>
              <CardTitle className="text-xl">Pull in fresh roles</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Run a scan any time you want another pass across current openings.
            </CardContent>
          </Card>
        </div>
        <ShellSection surface="muted">
          <EmptyState
            title="No matches yet"
            description="Upload your CV and set preferences to get started."
            action={
              <div className="flex flex-wrap items-center gap-2">
                <Button asChild variant="outline">
                  <Link href="/app/documents">Upload your CV</Link>
                </Button>
                <Button asChild variant="soft">
                  <Link href="/app/matches/settings">Update preferences</Link>
                </Button>
              </div>
            }
          />
        </ShellSection>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {header}

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Showing now</p>
            <CardTitle className="text-3xl text-primary">{matches.length}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Roles on this page ready for review.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Fresh this round</p>
            <CardTitle className="text-3xl text-primary">{newMatches}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            New roles you have not reviewed yet.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Strong fit</p>
            <CardTitle className="text-3xl text-primary">{highFitMatches}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline">{appliedMatches} applied</Badge>
            High-confidence matches are highlighted first.
          </CardContent>
        </Card>
      </div>

      <ShellSection>
        <ShellSectionHeader>
          <ShellSectionHeaderContent>
            <ShellSectionHeaderTitle>Latest roles</ShellSectionHeaderTitle>
            <ShellSectionHeaderDescription>
              Browse in place, then branch into apply, swipe, or outreach when a role is worth
              pursuing.
            </ShellSectionHeaderDescription>
          </ShellSectionHeaderContent>
          <ShellSectionHeaderActions className="text-sm text-muted-foreground">
            Page {offset / limit + 1} of {Math.max(1, Math.ceil(data.total / limit))}
          </ShellSectionHeaderActions>
        </ShellSectionHeader>

        <div className="grid gap-4">
          {matches.map((match) => (
            <MatchCard key={match.matchId} match={match} />
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-4 text-sm text-muted-foreground">
          <span>
            Showing {offset + 1}-{Math.min(offset + limit, data.total)} of {data.total} matches
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
    </div>
  );
}
