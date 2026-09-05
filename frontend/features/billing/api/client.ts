import { requestData } from "@/src/lib/api-client";
import type { CheckoutSession, PortalSession, SubscriptionStatus } from "@/src/lib/types";

export function fetchSubscriptionStatus(): Promise<SubscriptionStatus> {
  return requestData<SubscriptionStatus>("/api/billing/subscription");
}

export function createCheckoutSession(options?: {
  successUrl?: string;
  cancelUrl?: string;
}): Promise<CheckoutSession> {
  return requestData<CheckoutSession>("/api/billing/checkout-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options ?? {}),
  });
}

export function createPortalSession(options?: { returnUrl?: string }): Promise<PortalSession> {
  return requestData<PortalSession>("/api/billing/portal-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options ?? {}),
  });
}
