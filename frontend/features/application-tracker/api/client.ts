import type { ApplicationStatus, TrackedMatch, TrackedMatchListResponse } from "@/src/lib/types";

export async function fetchTrackedMatches(
  status: ApplicationStatus | undefined,
  sort: string,
  limit: number,
  offset: number,
): Promise<TrackedMatchListResponse> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("sort", sort);
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  const res = await fetch(`/api/application-tracker/matches?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch tracked matches: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function updateApplicationStatus(
  matchId: string,
  status: ApplicationStatus,
): Promise<TrackedMatch> {
  const res = await fetch(`/api/application-tracker/matches/${matchId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ application_status: status }),
  });
  if (!res.ok) throw new Error(`Failed to update application status: ${res.status}`);
  const json = await res.json();
  return json.data;
}
