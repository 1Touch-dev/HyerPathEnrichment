import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/**
 * BFF proxy for transitioning a sourced lead's review status (machine-2/12).
 * Forwards only to this app's own backend, never to linkedin.com.
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

const ALLOWED_STATUSES = new Set(["reviewed", "contacted", "dismissed"]);

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = (await request.json()) as { status?: string };

  if (!body.status || !ALLOWED_STATUSES.has(body.status)) {
    return bffValidationError("status must be one of reviewed, contacted, dismissed.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/linkedin-sourcing/leads/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: body.status }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendSourcedLead);
}
