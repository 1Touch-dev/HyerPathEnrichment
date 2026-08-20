"use client";

import { Button } from "@/components/ui/button";
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

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border p-4">
      <div className="min-w-[12rem] flex-1">
        <p className="font-medium">{match.title}</p>
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

      {/* Populated once Module D's interview scheduling ships (nextInterviewAt is always
          null until then) — intentionally renders nothing rather than a placeholder chip. */}
      {match.nextInterviewAt && (
        <div className="text-xs text-muted-foreground">
          Interview: {new Date(match.nextInterviewAt).toLocaleString()}
        </div>
      )}

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
      </div>
    </div>
  );
}
