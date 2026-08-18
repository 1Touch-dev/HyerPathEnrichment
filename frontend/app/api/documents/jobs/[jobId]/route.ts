import { NextRequest } from "next/server";
import { BackendJobStatusResponse, mapBackendDocumentJobStatus } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/**
 * Thin proxy for the backend's existing `GET /api/documents/jobs/{job_id}`
 * (get_job_status, backend/app/modules/documents/router.py) — the real async-job-status
 * signal, used to poll CV-feedback generation (§8.9) since `CvFeedbackReport` has no
 * interim "pending" row to poll instead (see backend/app/workers/tasks/cv_improvement.py).
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/jobs/${jobId}`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, (payload: BackendJobStatusResponse) =>
    mapBackendDocumentJobStatus(payload),
  );
}
