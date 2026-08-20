"use client";

import { JobCard } from "@/components/dossier/JobCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import type { JobMatch } from "@/src/lib/types";
import { getApplyRedirectUrl } from "../api/client";
import { useMarkApplied, useMarkMatchViewed, useSubmitFeedback } from "../hooks/useMatches";
import { useEffect } from "react";

interface MatchCardProps {
  match: JobMatch;
}

function scoreColor(score: number): string {
  if (score >= 80) return "bg-green-100 text-green-800";
  if (score >= 60) return "bg-yellow-100 text-yellow-800";
  return "bg-gray-100 text-gray-600";
}

export function MatchCard({ match }: MatchCardProps) {
  const markViewed = useMarkMatchViewed();
  const submitFeedback = useSubmitFeedback();
  const markApplied = useMarkApplied();
  const belowSimilarityThreshold = match.scoreBreakdown.below_similarity_threshold === true;

  useEffect(() => {
    if (match.isNew) {
      markViewed.mutate(match.matchId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [match.matchId]);

  return (
    <div className="relative rounded-lg border p-4">
      <div className="absolute right-4 top-4">
        {belowSimilarityThreshold ? (
          <Badge className="bg-muted text-muted-foreground">Broader match</Badge>
        ) : (
          <Badge className={scoreColor(match.overallScore)}>
            {Math.round(match.overallScore)}/100
          </Badge>
        )}
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
        <p className="mt-2 text-sm text-muted-foreground">{match.explanation}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button size="sm" asChild>
          <a href={getApplyRedirectUrl(match.matchId)} target="_blank" rel="noopener noreferrer">
            Apply
          </a>
        </Button>

        <div className="flex items-center gap-2">
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

        <div className="ml-auto flex gap-1">
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
    </div>
  );
}
