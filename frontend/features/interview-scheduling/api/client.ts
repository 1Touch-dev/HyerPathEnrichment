import type { InterviewSchedule } from "@/src/lib/types";

export interface ScheduleInterviewInput {
  /** UTC ISO string — already converted from the picked local wall-clock time (§8.3). */
  scheduledAt: string;
  durationMinutes: number;
  notes: string | null;
}

export async function fetchInterviewSchedule(matchId: string): Promise<InterviewSchedule | null> {
  const res = await fetch(`/api/interviews/matches/${matchId}/schedule`);
  if (!res.ok) throw new Error(`Failed to fetch interview schedule: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function scheduleInterview(
  matchId: string,
  input: ScheduleInterviewInput,
): Promise<InterviewSchedule> {
  const res = await fetch(`/api/interviews/matches/${matchId}/schedule`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scheduled_at: input.scheduledAt,
      duration_minutes: input.durationMinutes,
      notes: input.notes,
    }),
  });
  if (!res.ok) throw new Error(`Failed to schedule interview: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function cancelInterview(matchId: string): Promise<void> {
  const res = await fetch(`/api/interviews/matches/${matchId}/schedule`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to cancel interview: ${res.status}`);
}
