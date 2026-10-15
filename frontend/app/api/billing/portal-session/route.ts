import { NextRequest } from "next/server";
import { adaptPortalSession } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  handleBackendJson,
} from "@/src/lib/bff-response";
import { getPublicAppOrigin } from "@/src/lib/public-app-url";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const origin = getPublicAppOrigin(request);
  let body: { returnUrl?: string } = {};
  try {
    body = (await request.json()) as typeof body;
  } catch {
    body = {};
  }

  const returnUrl = body.returnUrl ?? `${origin}/app/settings`;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/billing/portal-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ return_url: returnUrl }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(backendResponse, adaptPortalSession);
}
