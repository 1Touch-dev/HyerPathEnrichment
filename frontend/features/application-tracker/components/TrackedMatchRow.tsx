"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getApplyRedirectUrl } from "@/features/job-matching/api/client";
import { useMarkApplied } from "@/features/job-matching/hooks/useMatches";
import { InterviewScheduleCard } from "@/features/interview-scheduling";
import type { ApplicationStatus, TrackedMatch } from "@/src/lib/types";
import { useUpdateApplicationStatus } from "../hooks/useUpdateApplicationStatus";
import { StatusBadge } from "./StatusBadge";

const STATUS_OPTIONS: ApplicationStatus[] = [
  "new",
  "applied",
  "replied",
  "interview",
  "offer",
  "rejected",
];

interface TrackedMatchRowProps {
  match: TrackedMatch;
}

export function TrackedMatchRow({ match }: TrackedMatchRowProps) {
  const updateStatus = useUpdateApplicationStatus();
  const markApplied = useMarkApplied();

  // Module F: manual entries have no similarity/rule score to compute — `overallScore`
  // is the only field the backend guarantees is `null` exclusively for these rows
  // (§10.6), so it doubles as the "is this a manually-added entry" signal here rather
  // than introducing a second, redundant `isManual` flag.
  const isManualEntry = match.overallScore === null;

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center gap-4">
        <div className="min-w-[12rem] flex-1">
          <div className="flex items-center gap-2">
            <p className="font-medium">{match.title}</p>
            {isManualEntry && (
              <Badge variant="secondary" title="Added manually — not from an automated scan">
                Manually added
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground">{match.company}</p>
          {(match.location || match.remote) && (
            <p className="text-xs text-muted-foreground">
              {match.remote ? "Remote" : match.location}
            </p>
          )}
        </div>

        <div className="w-16 text-center">
          {match.overallScore === null ? (
            <span className="text-sm text-muted-foreground" title="Manually added — no match score">
              —
            </span>
          ) : (
            <span className="text-sm font-medium">{Math.round(match.overallScore)}/100</span>
          )}
        </div>

        <div>
          <StatusBadge status={match.applicationStatus} />
        </div>

        <Select
          value={match.applicationStatus}
          onValueChange={(value) =>
            updateStatus.mutate({ matchId: match.matchId, status: value as ApplicationStatus })
          }
          disabled={updateStatus.isPending}
        >
          <SelectTrigger className="w-[150px]" aria-label="Application status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((status) => (
              <SelectItem key={status} value={status}>
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="ml-auto flex items-center gap-3">
          {isManualEntry ? (
            // Module B's apply-redirect endpoint is job_posting_id-keyed and manual
            // entries have none — a manual row gets a plain link to whatever URL the
            // candidate provided (no click-tracking redirect), and no Apply affordance
            // at all if they didn't provide one, rather than a broken redirect (§10.7).
            match.sourceUrl && (
              <Button size="sm" asChild>
                <a href={match.sourceUrl} target="_blank" rel="noopener noreferrer">
                  Apply
                </a>
              </Button>
            )
          ) : (
            <Button size="sm" asChild>
              <a
                href={getApplyRedirectUrl(match.matchId)}
                target="_blank"
                rel="noopener noreferrer"
              >
                Apply
              </a>
            </Button>
          )}

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
        </div>
      </div>

      {/* Module D: interview scheduling — shown inline once this application's
          status is "interview", regardless of whether a schedule already exists
          (InterviewScheduleCard itself renders the "Schedule interview" CTA when
          useInterviewSchedule resolves to null, per §15.5). */}
      {match.applicationStatus === "interview" && <InterviewScheduleCard matchId={match.matchId} />}
    </div>
  );
}
