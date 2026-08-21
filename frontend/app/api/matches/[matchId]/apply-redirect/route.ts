import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable } from "@/src/lib/bff-response";

/**
 * Thin pass-through redirect: the backend is never directly reachable from the
 * browser (no `NEXT_PUBLIC_API_BASE_URL`), so we can't just point the "Apply"
 * link's `href` at the backend origin the way `auth/google/authorize/route.ts`
 * does for an already-public OAuth redirect. Instead this route runs the
 * authenticated `backendFetch` server-side with `redirect: "manual"` to capture
 * the backend's 302 `Location` (the job posting's own `source_url`, per the
 * open-redirect guard in the backend's `apply_redirect` handler) without ever
 * following it itself, then re-issues that exact same target as a same-origin
 * `NextResponse.redirect` the browser tab can follow. This also means the
 * click-tracking side effect on the backend (`record_apply_click`) still runs
 * exactly once per navigation, since the backend, not this route, decides the
 * target URL.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/job-matching/matches/${matchId}/apply-redirect`, {
      redirect: "manual",
    });
  } catch {
    return bffServiceUnavailable();
  }

  const location = backendResponse.headers.get("location");
  if (backendResponse.status >= 300 && backendResponse.status < 400 && location) {
    return NextResponse.redirect(location, 302);
  }

  return backendFailureResponse(backendResponse);
}
