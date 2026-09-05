import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  bffSuccess,
  bffValidationError,
} from "@/src/lib/bff-response";

type PushSubscribeBody = {
  endpoint?: string;
  p256dh?: string;
  auth?: string;
};

type PushUnsubscribeBody = {
  endpoint?: string;
};

export async function POST(request: NextRequest) {
  const body = (await request.json()) as PushSubscribeBody;

  if (!body.endpoint || !body.p256dh || !body.auth) {
    return bffValidationError("endpoint, p256dh, and auth are required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/job-matching/push-subscription", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint: body.endpoint,
        p256dh: body.p256dh,
        auth: body.auth,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }

  // Backend returns 204 No Content — nothing to unwrap/map.
  return bffSuccess(null);
}

export async function DELETE(request: NextRequest) {
  const body = (await request.json()) as PushUnsubscribeBody;

  if (!body.endpoint) {
    return bffValidationError("endpoint is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/job-matching/push-subscription", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: body.endpoint }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }

  // Backend returns 204 No Content — nothing to unwrap/map.
  return bffSuccess(null);
}
