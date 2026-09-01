import { NextRequest } from "next/server";
import { adaptCheckoutSession } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const origin = request.nextUrl.origin;
  let body: { successUrl?: string; cancelUrl?: string } = {};
  try {
    body = (await request.json()) as typeof body;
  } catch {
    body = {};
  }

  const successUrl = body.successUrl ?? `${origin}/app/settings?billing=success`;
  const cancelUrl = body.cancelUrl ?? `${origin}/app/settings?billing=cancel`;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/billing/checkout-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ success_url: successUrl, cancel_url: cancelUrl }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(backendResponse, adaptCheckoutSession);
}
