import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable } from "@/src/lib/bff-response";

/**
 * Fetches the backend's `.ics` file server-side and returns its body/headers
 * directly, rather than a redirect. Unlike Module B's apply-redirect (a 3xx to an
 * external job-posting URL the backend already validated), this endpoint's
 * "target" *is* the backend itself — there is nothing else to redirect to, and
 * the backend is never directly browser-reachable (no `NEXT_PUBLIC_API_BASE_URL`).
 * A redirect chain would just point the browser at an unreachable origin. The
 * `.ics` body is a small hand-built text file (see backend's `ics_builder.py`),
 * not a large binary, so buffering it through this route and re-emitting it with
 * the same `Content-Type`/`Content-Disposition` headers is simpler and more
 * reliable than trying to stream/redirect — there's no meaningful latency or
 * memory cost to justify the extra complexity of a streaming passthrough here.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/interviews/matches/${matchId}/schedule.ics`);
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }

  const body = await backendResponse.arrayBuffer();
  const contentType = backendResponse.headers.get("content-type") ?? "text/calendar; charset=utf-8";
  const contentDisposition = backendResponse.headers.get("content-disposition") ?? "attachment";

  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": contentDisposition,
    },
  });
}
