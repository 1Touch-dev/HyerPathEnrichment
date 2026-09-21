"use client";

import { useEffect } from "react";
import { UpgradeButton } from "@/features/billing";
import { JobCard } from "@/components/dossier/JobCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { CandidatePolicyLink, useAppShellAccess } from "@/components/layout/app-shell-access";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { JobMatch } from "@/src/lib/types";
import { getApplyRedirectUrl } from "../api/client";
import { useMarkApplied, useMarkMatchViewed, useSubmitFeedback } from "../hooks/useMatches";

interface MatchCardProps {
  match: JobMatch;
}

function scoreBadge(match: JobMatch) {
  if (match.scoreBreakdown.below_similarity_threshold === true) {
    return <Badge variant="secondary">Broader match</Badge>;
  }

  if (match.overallScore >= 80) {
    return <Badge variant="success">{Math.round(match.overallScore)}/100</Badge>;
  }

  if (match.overallScore >= 60) {
    return <Badge variant="warning">{Math.round(match.overallScore)}/100</Badge>;
  }

  return <Badge variant="outline">{Math.round(match.overallScore)}/100</Badge>;
}

export function MatchCard({ match }: MatchCardProps) {
  const { candidateMutationsAllowed } = useAppShellAccess();
  const markViewed = useMarkMatchViewed();
  const submitFeedback = useSubmitFeedback();
  const markApplied = useMarkApplied();
  const belowSimilarityThreshold = match.scoreBreakdown.below_similarity_threshold === true;

  useEffect(() => {
    if (candidateMutationsAllowed && match.isNew) {
      markViewed.mutate(match.matchId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidateMutationsAllowed, match.matchId]);

  return (
    <div className="app-surface-muted flex flex-col gap-4 rounded-[1.25rem] p-5 transition-colors hover:border-ring/30">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {scoreBadge(match)}
          {match.isNew ? <Badge variant="info">New</Badge> : null}
          {match.appliedAt ? <Badge variant="outline">Applied</Badge> : null}
        </div>
        <div className="flex items-center gap-1 rounded-full bg-surface px-1 py-1">
          <Button
            size="icon"
            variant={match.feedback === "up" ? "default" : "ghost"}
            onClick={() => submitFeedback.mutate({ matchId: match.matchId, feedback: "up" })}
            aria-label="Good match"
          >
            <ThumbsUp className="h-4 w-4" />
          </Button>
          <Button
            size="icon"
            variant={match.feedback === "down" ? "default" : "ghost"}
            onClick={() => submitFeedback.mutate({ matchId: match.matchId, feedback: "down" })}
            aria-label="Not a good match"
          >
            <ThumbsDown className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <JobCard
        job={{
          title: match.title,
          company: match.company,
          location: match.location ?? "",
          remote: match.remote,
          source: match.source,
        }}
      />

      {match.explanation && (
        <div className={match.isBlurred ? "relative" : undefined}>
          <p
            className={
              match.isBlurred
                ? "rounded-xl bg-surface/80 px-4 py-3 text-sm text-muted-foreground blur-sm select-none"
                : "rounded-xl bg-surface/80 px-4 py-3 text-sm text-muted-foreground"
            }
          >
            {match.explanation}
          </p>
          {match.isBlurred ? (
            <div className="mt-2 flex items-center gap-2">
              <UpgradeButton />
            </div>
          ) : null}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 border-t border-border/60 pt-1">
        <Button size="sm" asChild>
          <CandidatePolicyLink
            href={getApplyRedirectUrl(match.matchId)}
            target="_blank"
            rel="noopener noreferrer"
          >
            Apply
          </CandidatePolicyLink>
        </Button>

        <div className="flex items-center gap-2 rounded-full bg-surface px-3 py-2">
          <Checkbox
            id={`applied-${match.matchId}`}
            checked={match.appliedAt !== null}
            onCheckedChange={(checked) =>
              markApplied.mutate({ matchId: match.matchId, applied: checked === true })
            }
          />
          <Label htmlFor={`applied-${match.matchId}`} className="text-sm text-muted-foreground">
            Mark as applied
          </Label>
        </div>
        {belowSimilarityThreshold ? (
          <p className="text-sm text-muted-foreground">
            Worth a look if you are open to adjacent roles.
          </p>
        ) : null}
      </div>
    </div>
  );
}
