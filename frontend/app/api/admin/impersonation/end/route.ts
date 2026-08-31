import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, bffSuccess } from "@/src/lib/bff-response";
import { forwardBackendSetCookies } from "@/src/lib/forward-backend-cookies";

export async function POST() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/impersonation/end", { method: "POST" });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }

  // Backend returns 204 No Content and clears the `access_token` cookie
  // (backend/app/modules/admin/impersonation.py) — forward it, matching the
  // existing Set-Cookie relay pattern in app/api/auth/login/route.ts.
  const bffResponse = bffSuccess(null);
  forwardBackendSetCookies(backendResponse, bffResponse);
  return bffResponse;
}
