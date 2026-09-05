import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/**
 * BFF proxy for the LinkedIn sourcing lead queue (machine-2/12). This route
 * only forwards a human-typed lead-entry form submission (or a list query)
 * to this app's own backend — it never calls linkedin.com or any
 * third-party site, and performs no autofill of any kind.
 */
interface BackendSourcedLead {
  id: string;
  sourced_by: string | null;
  full_name: string;
  headline: string | null;
  location: string | null;
  linkedin_profile_url: string;
  target_role: string | null;
  notes: string | null;
  status: string;
  created_at: string;
}

function mapBackendSourcedLead(raw: BackendSourcedLead) {
  return {
    id: raw.id,
    sourcedBy: raw.sourced_by,
    fullName: raw.full_name,
    headline: raw.headline,
    location: raw.location,
    linkedinProfileUrl: raw.linkedin_profile_url,
    targetRole: raw.target_role,
    notes: raw.notes,
    status: raw.status,
    createdAt: raw.created_at,
  };
}

export async function GET(request: NextRequest) {
  const statusFilter = request.nextUrl.searchParams.get("status");
  const query = new URLSearchParams();
  if (statusFilter) query.set("status", statusFilter);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/linkedin-sourcing/leads?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (raw: BackendSourcedLead[]) =>
    raw.map(mapBackendSourcedLead),
  );
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as {
    fullName?: string;
    headline?: string | null;
    location?: string | null;
    linkedinProfileUrl?: string;
    targetRole?: string | null;
    notes?: string | null;
  };

  if (!body.fullName || typeof body.fullName !== "string" || !body.fullName.trim()) {
    return bffValidationError("fullName is required.");
  }
  if (
    !body.linkedinProfileUrl ||
    typeof body.linkedinProfileUrl !== "string" ||
    !body.linkedinProfileUrl.trim()
  ) {
    return bffValidationError("linkedinProfileUrl is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/linkedin-sourcing/leads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: body.fullName,
        headline: body.headline ?? null,
        location: body.location ?? null,
        linkedin_profile_url: body.linkedinProfileUrl,
        target_role: body.targetRole ?? null,
        notes: body.notes ?? null,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendSourcedLead, 201);
}
