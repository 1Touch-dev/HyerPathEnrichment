import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable } from "@/src/lib/bff-response";

// Long-lived stream: skip static optimization and give the backend fetch more
// room than the default request timeout (matches backend job_matching events max_seconds).
export const dynamic = "force-dynamic";
const SSE_FETCH_TIMEOUT_MS = 320_000;

const SSE_HEADERS = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache, no-transform",
  Connection: "keep-alive",
  "X-Accel-Buffering": "no",
};

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      "/api/job-matching/events",
      { headers: { Accept: "text/event-stream" } },
      SSE_FETCH_TIMEOUT_MS,
    );
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok || !backendResponse.body) {
    console.warn(`[SSE /api/job-matching/events] Backend returned ${backendResponse.status}`);
    return backendFailureResponse(backendResponse);
  }

  return new Response(backendResponse.body, { status: 200, headers: SSE_HEADERS });
}
