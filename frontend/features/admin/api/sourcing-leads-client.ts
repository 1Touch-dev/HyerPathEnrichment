/**
 * Plain fetch client for the LinkedIn sourcing lead queue (machine-2/12).
 *
 * Kept as its own isolated file (not merged into `./client.ts`) because a
 * sibling chunk (RBAC admin frontend) edits `./client.ts` concurrently — see
 * task-orchestration/machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md.
 *
 * Every field this client sends comes from a human manually typing/pasting
 * what they observed on a LinkedIn profile themselves — there is no
 * URL-paste-and-autofill behavior anywhere in this module, and no request
 * here ever targets linkedin.com or any third-party site; all three
 * functions below only call this app's own `/api/linkedin-sourcing/leads`
 * BFF routes.
 */

export type SourcedLeadStatus = "new" | "reviewed" | "contacted" | "dismissed";

export interface SourcedCandidateLead {
  id: string;
  sourcedBy: string | null;
  fullName: string;
  headline: string | null;
  location: string | null;
  linkedinProfileUrl: string;
  targetRole: string | null;
  notes: string | null;
  status: SourcedLeadStatus;
  createdAt: string;
}

export interface CreateSourcedLeadInput {
  fullName: string;
  headline?: string | null;
  location?: string | null;
  linkedinProfileUrl: string;
  targetRole?: string | null;
  notes?: string | null;
}

async function unwrap<T>(res: Response, errorLabel: string): Promise<T> {
  if (!res.ok) throw new Error(`${errorLabel}: ${res.status}`);
  const json = await res.json();
  return json.data as T;
}

export async function listLeads(
  status?: SourcedLeadStatus | null,
): Promise<SourcedCandidateLead[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const res = await fetch(`/api/linkedin-sourcing/leads?${params.toString()}`);
  return unwrap(res, "Failed to fetch sourced leads");
}

export async function createLead(body: CreateSourcedLeadInput): Promise<SourcedCandidateLead> {
  const res = await fetch("/api/linkedin-sourcing/leads", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return unwrap(res, "Failed to create sourced lead");
}

export async function reviewLead(
  id: string,
  status: "reviewed" | "contacted" | "dismissed",
): Promise<SourcedCandidateLead> {
  const res = await fetch(`/api/linkedin-sourcing/leads/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return unwrap(res, "Failed to update lead status");
}
