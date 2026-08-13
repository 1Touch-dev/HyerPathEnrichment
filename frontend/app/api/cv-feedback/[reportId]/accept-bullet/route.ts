import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, bffSuccess, bffValidationError } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

// DEVIATION from phase2_module2.md §11.4's literal snippet (which posts to a flat
// `/api/cv-feedback/{reportId}/accept-bullet` backend route): the real, merged backend
// route is `POST /api/documents/{document_id}/feedback/{report_id}/accept`
// (backend/app/modules/documents/router.py), which is nested under document_id and
// returns the full CvFeedbackResponse — not a flat `{accepted: true}`. Reconciled here to
// call the real backend route and to expose the shape `acceptCvBullet()` in
// src/lib/api-client.ts already expects. See final report: `documentId` is read from the
// JSON body defensively, but src/lib/api-client.ts's `acceptCvBullet(reportId, bulletIndex)`
// does not currently send one — this is a gap in that foundation function, flagged rather
// than fixed here per scope.
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ reportId: string }> },
) {
  const { reportId } = await params;
  const body = await request.json().catch(() => null);

  if (typeof body?.bulletIndex !== "number") {
    return bffValidationError("bulletIndex is required.");
  }
  if (typeof body?.documentId !== "string" || !body.documentId) {
    return bffValidationError(
      "documentId is required to accept a CV feedback bullet (backend route is scoped by document).",
    );
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      `/api/documents/${body.documentId}/feedback/${reportId}/accept`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bullet_index: body.bulletIndex }),
      },
    );
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }
  return bffSuccess({ accepted: true });
}
