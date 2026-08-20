"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useScheduleInterview } from "../hooks/useScheduleInterview";

interface ScheduleInterviewDialogProps {
  matchId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Native `<input type="datetime-local">` has no timezone concept of its own — the
 * candidate always enters the time in their own browser's local wall clock. Converted
 * to a UTC ISO string via `new Date(localValue).toISOString()` before POSTing, per
 * §8.3's timezone-handling note.
 */
export function ScheduleInterviewDialog({
  matchId,
  open,
  onOpenChange,
}: ScheduleInterviewDialogProps) {
  const scheduleInterview = useScheduleInterview(matchId);
  const [localDateTime, setLocalDateTime] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  function resetForm() {
    setLocalDateTime("");
    setDurationMinutes(60);
    setNotes("");
    setFormError(null);
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetForm();
      scheduleInterview.reset();
    }
    onOpenChange(nextOpen);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!localDateTime) {
      setFormError("Date and time are required.");
      return;
    }

    const parsed = new Date(localDateTime);
    if (Number.isNaN(parsed.getTime())) {
      setFormError("Please choose a valid date and time.");
      return;
    }

    setFormError(null);
    scheduleInterview.mutate(
      {
        scheduledAt: parsed.toISOString(),
        durationMinutes,
        notes: notes.trim() ? notes.trim() : null,
      },
      {
        onSuccess: () => handleOpenChange(false),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Schedule interview</DialogTitle>
            <DialogDescription>
              Pick a date and time in your local timezone — we&apos;ll convert it automatically.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="interview-datetime">Date &amp; time</Label>
              <Input
                id="interview-datetime"
                type="datetime-local"
                value={localDateTime}
                onChange={(e) => setLocalDateTime(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="interview-duration">Duration (minutes)</Label>
              <Input
                id="interview-duration"
                type="number"
                min={15}
                max={480}
                step={15}
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="interview-notes">Notes</Label>
              <Textarea
                id="interview-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Interviewer name, meeting link, prep reminders…"
              />
            </div>

            {(formError || scheduleInterview.isError) && (
              <p className="text-sm text-destructive">
                {formError ?? "Couldn't schedule the interview. Please try again."}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={scheduleInterview.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={scheduleInterview.isPending}>
              {scheduleInterview.isPending ? "Scheduling…" : "Schedule interview"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
