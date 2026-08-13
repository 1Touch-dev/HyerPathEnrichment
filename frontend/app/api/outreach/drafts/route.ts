import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, bffValidationError, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/**
 * Real backend contract (backend/app/modules/outreach/schemas.py::OutreachDraftRequest,
 * cross-checked directly against the merged router/schema — phase2_module2.md §11.7's
 * `job_posting_id`-based snippet is stale here): `company_name` and `document_id` are
 * required; `recipient_role_title` and `job_match_id` are optional. There is no
 * `job_posting_id` field anywhere in the outreach module, so it is validated (to match the
 * already-merged `draftOutreach()` in `src/lib/api-client.ts`, which only sends
 * `{jobPostingId, documentId}`) but intentionally NOT forwarded to the backend — see this
 * chunk's report for why (no safe mapping exists from a job-posting/match id to the
 * required `company_name`). `companyName`/`recipientRoleTitle`/`jobMatchId` are accepted
 * here too, for forward-compatibility once a caller supplies them; until then the backend
 * will reject the request with its own 422 for the missing `company_name`, surfaced as-is
 * through `handleBackendJson`/`backendFailureResponse`.
 *
 * Drafting is async (OutreachService.request_draft enqueues an RQ job and returns
 * `{rq_job_id, message}` immediately — the draft itself appears later via `GET /api/outreach`
 * once the worker finishes), so there is no `OutreachMessage` to adapt here.
 */
export async function POST(request: NextRequest) {
  const body = await request.json();

  if (typeof body?.jobPostingId !== "string") {
    return bffValidationError("jobPostingId is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/outreach/drafts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document_id: body.documentId ?? null,
        company_name: body.companyName ?? null,
        recipient_role_title: body.recipientRoleTitle ?? null,
        job_match_id: body.jobMatchId ?? null,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(
    backendResponse,
    (raw: { rq_job_id: string; message: string }) => ({ rqJobId: raw.rq_job_id, message: raw.message }),
    202,
  );
}
