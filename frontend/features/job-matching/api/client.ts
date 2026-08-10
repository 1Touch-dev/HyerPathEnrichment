import type { CandidateJobPreferences, JobMatchListResponse } from "@/src/lib/types";

export async function fetchPreferences(): Promise<CandidateJobPreferences> {
  const res = await fetch("/api/job-matching/preferences");
  if (!res.ok) throw new Error(`Failed to fetch preferences: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function updatePreferences(
  payload: Partial<CandidateJobPreferences>,
): Promise<CandidateJobPreferences> {
  const res = await fetch("/api/job-matching/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to update preferences: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function fetchMatches(limit: number, offset: number): Promise<JobMatchListResponse> {
  const res = await fetch(`/api/job-matching/matches?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`Failed to fetch matches: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function markMatchViewed(matchId: string): Promise<void> {
  await fetch(`/api/job-matching/matches/${matchId}/view`, { method: "POST" });
}

export async function submitMatchFeedback(matchId: string, feedback: "up" | "down"): Promise<void> {
  await fetch(`/api/job-matching/matches/${matchId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
}

export async function triggerScan(): Promise<{ scanEnqueued: boolean }> {
  const res = await fetch("/api/job-matching/scan", { method: "POST" });
  if (!res.ok) throw new Error(`Failed to trigger scan: ${res.status}`);
  const json = await res.json();
  return { scanEnqueued: json.data.scanEnqueued };
}
