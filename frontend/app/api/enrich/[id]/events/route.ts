import { NextRequest } from "next/server";
import { backendFailureResponse, bffError, bffServiceUnavailable } from "@/src/lib/bff-response";
import { backendFetch } from "@/src/lib/backend-client";
import { isMockMode } from "@/src/lib/mocks/enabled";
import { getMockJob } from "@/src/lib/mocks/mock-jobs";
import { JobStatus } from "@/src/lib/types";

// Long-lived stream: skip static optimization and give the backend fetch more
// room than the default request timeout (matches backend job_events max_seconds).
export const dynamic = "force-dynamic";
const SSE_FETCH_TIMEOUT_MS = 320_000;
const MOCK_POLL_MS = 400;

const SSE_HEADERS = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache, no-transform",
  Connection: "keep-alive",
  "X-Accel-Buffering": "no",
};

const TERMINAL_STATUSES: readonly JobStatus[] = ["completed", "failed", "suppressed"];

function sseEvent(jobId: string, status: JobStatus): Uint8Array {
  return new TextEncoder().encode(`data: ${JSON.stringify({ job_id: jobId, status })}\n\n`);
}

function mockEventStream(jobId: string): ReadableStream<Uint8Array> {
  let timer: ReturnType<typeof setInterval> | null = null;
  return new ReadableStream<Uint8Array>({
    start(controller) {
      timer = setInterval(() => {
        const job = getMockJob(jobId);
        if (!job || !TERMINAL_STATUSES.includes(job.status)) {
          return;
        }
        controller.enqueue(sseEvent(jobId, job.status));
        if (timer) clearInterval(timer);
        controller.close();
      }, MOCK_POLL_MS);
    },
    cancel() {
      if (timer) clearInterval(timer);
    },
  });
}

export async function GET(_request: NextRequest, { params }: { params: { id: string } }) {
  const jobId = params.id;

  if (isMockMode()) {
    const job = getMockJob(jobId);
    if (!job) {
      return bffError("NOT_FOUND", "Job not found.", 404);
    }
    return new Response(mockEventStream(jobId), { status: 200, headers: SSE_HEADERS });
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      `/enrich/${jobId}/events`,
      { headers: { Accept: "text/event-stream" } },
      SSE_FETCH_TIMEOUT_MS,
    );
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok || !backendResponse.body) {
    return backendFailureResponse(backendResponse);
  }

  return new Response(backendResponse.body, { status: 200, headers: SSE_HEADERS });
}
