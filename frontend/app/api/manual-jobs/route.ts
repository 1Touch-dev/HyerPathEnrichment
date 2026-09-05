import { NextRequest } from "next/server";
import { BackendManualJobEntryResponse, mapBackendManualJobEntry } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as {
    title?: string;
    company?: string;
    location?: string | null;
    source_label?: string | null;
    source_url?: string | null;
    notes?: string | null;
  };

  if (!body.title || typeof body.title !== "string" || !body.title.trim()) {
    return bffValidationError("title is required.");
  }
  if (!body.company || typeof body.company !== "string" || !body.company.trim()) {
    return bffValidationError("company is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/manual-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: body.title,
        company: body.company,
        location: body.location ?? null,
        source_label: body.source_label ?? null,
        source_url: body.source_url ?? null,
        notes: body.notes ?? null,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendManualJobEntryResponse) =>
    mapBackendManualJobEntry(payload),
  );
}
