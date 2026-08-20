"use client";

import { useState } from "react";
import Link from "next/link";
import { CalendarPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCancelInterview } from "../hooks/useCancelInterview";
import { useInterviewSchedule } from "../hooks/useInterviewSchedule";
import { ScheduleInterviewDialog } from "./ScheduleInterviewDialog";

interface InterviewScheduleCardProps {
  matchId: string;
}

/**
 * Loading/error/empty states follow §15.5's exact matrix for this component:
 * skeleton while loading, an inline error with no retry button (low-stakes GET,
 * a page refresh is an adequate fallback), and — when the query resolves to
 * `null` — a "Schedule interview" CTA instead of the card, since that's the
 * expected common case (no interview scheduled yet), not an error.
 */
export function InterviewScheduleCard({ matchId }: InterviewScheduleCardProps) {
  const { data: schedule, isLoading, isError } = useInterviewSchedule(matchId);
  const cancelInterview = useCancelInterview(matchId);
  const [dialogOpen, setDialogOpen] = useState(false);

  if (isLoading) {
    return <Skeleton className="h-36 w-full rounded-lg" />;
  }

  if (isError) {
    return (
      <p className="text-sm text-destructive" role="alert">
        Couldn&apos;t load the interview schedule. Refresh the page to try again.
      </p>
    );
  }

  if (!schedule) {
    return (
      <>
        <Button size="sm" variant="outline" onClick={() => setDialogOpen(true)}>
          Schedule interview
        </Button>
        <ScheduleInterviewDialog matchId={matchId} open={dialogOpen} onOpenChange={setDialogOpen} />
      </>
    );
  }

  // §8.3: scheduled_at is stored/transmitted in UTC; converting back via
  // toLocaleString(undefined, ...) renders it in whichever timezone the browser
  // currently reports, so the same instant displays correctly regardless of
  // where the candidate opens the app from later.
  const formattedDateTime = new Date(schedule.scheduledAt).toLocaleString(undefined, {
    dateStyle: "full",
    timeStyle: "short",
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Interview scheduled</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm font-medium">{formattedDateTime}</p>
        <p className="text-xs text-muted-foreground">{schedule.durationMinutes} minutes</p>
        {schedule.notes && <p className="text-sm text-muted-foreground">{schedule.notes}</p>}

        <div className="flex flex-wrap items-center gap-2 pt-2">
          <Button size="sm" variant="outline" asChild>
            <a href={schedule.icsDownloadUrl} download>
              <CalendarPlus className="mr-2 h-4 w-4" aria-hidden="true" />
              Add to Calendar (.ics)
            </a>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <a href={schedule.googleCalendarLink} target="_blank" rel="noopener noreferrer">
              <CalendarPlus className="mr-2 h-4 w-4" aria-hidden="true" />
              Google Calendar
            </a>
          </Button>
          <Button size="sm" variant="secondary" asChild>
            <Link href={`/app/practice?jobMatchId=${matchId}`}>Practice for this interview</Link>
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => cancelInterview.mutate()}
            disabled={cancelInterview.isPending}
          >
            {cancelInterview.isPending ? "Cancelling…" : "Cancel"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
