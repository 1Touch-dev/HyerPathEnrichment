import { NextRequest } from "next/server";
import { BackendJobStatusResponse, mapBackendDocumentJobStatus } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

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
