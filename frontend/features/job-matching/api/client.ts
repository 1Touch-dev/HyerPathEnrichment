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
  const res = await fetch(`/api/job-matching/matches/${matchId}/view`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to mark match viewed: ${res.status}`);
}

export async function submitMatchFeedback(matchId: string, feedback: "up" | "down"): Promise<void> {
  const res = await fetch(`/api/job-matching/matches/${matchId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
  if (!res.ok) throw new Error(`Failed to submit match feedback: ${res.status}`);
}

export async function triggerScan(): Promise<{ scanEnqueued: boolean }> {
  const res = await fetch("/api/job-matching/scan", { method: "POST" });
  if (!res.ok) throw new Error(`Failed to trigger scan: ${res.status}`);
  const json = await res.json();
  return { scanEnqueued: json.data.scanEnqueued };
}

export async function subscribeToPush(subscription: {
  endpoint: string;
  p256dh: string;
  auth: string;
}): Promise<void> {
  const res = await fetch("/api/job-matching/push-subscription", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscription),
  });
  if (!res.ok) throw new Error(`Failed to subscribe to push notifications: ${res.status}`);
}

export async function unsubscribeFromPush(endpoint: string): Promise<void> {
  const res = await fetch("/api/job-matching/push-subscription", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint }),
  });
  if (!res.ok) throw new Error(`Failed to unsubscribe from push notifications: ${res.status}`);
}
