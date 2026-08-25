import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/**
 * Real backend contract (backend/app/modules/outreach/schemas.py::OutreachDraftRequest,
 * cross-checked directly against the merged router/schema): `company_name` and
 * `document_id` are required; `recipient_role_title` and `job_match_id` are optional.
 * There is no `job_posting_id` field anywhere in the outreach module.
 *
 * Module 4, Module G (§11.4/§11.7): `message_type` (default `"email"`) and optional
 * `custom_instruction` (required by the service layer when `message_type === "custom"`,
 * validated backend-side, not here) were added to the same request schema.
 *
 * Drafting is async (OutreachService.request_draft enqueues an RQ job and returns
 * `{rq_job_id, message}` immediately — the draft itself appears later via `GET /api/outreach`
 * once the worker finishes), so there is no `OutreachMessage` to adapt here.
 */
export async function POST(request: NextRequest) {
  const body = await request.json();

  if (typeof body?.companyName !== "string" || !body.companyName.trim()) {
    return bffValidationError("companyName is required.");
  }
  if (typeof body?.documentId !== "string" || !body.documentId.trim()) {
    return bffValidationError("documentId is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/outreach/drafts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_name: body.companyName,
        document_id: body.documentId,
        recipient_role_title: body.recipientRoleTitle ?? null,
        job_match_id: body.jobMatchId ?? null,
        job_description: body.jobDescription ?? null,
        message_type: body.messageType ?? "email",
        custom_instruction: body.customInstruction ?? null,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(
    backendResponse,
    (raw: { rq_job_id: string; message: string }) => ({
      rqJobId: raw.rq_job_id,
      message: raw.message,
    }),
    202,
  );
}
