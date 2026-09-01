"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createCheckoutSession, createPortalSession, fetchSubscriptionStatus } from "../api/client";

export const billingKeys = {
  subscription: ["billing", "subscription"] as const,
};

export function useSubscription() {
  return useQuery({
    queryKey: billingKeys.subscription,
    queryFn: fetchSubscriptionStatus,
  });
}

export function useCheckout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCheckoutSession,
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url;
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: billingKeys.subscription });
    },
  });
}

export function useBillingPortal() {
  return useMutation({
    mutationFn: createPortalSession,
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url;
      }
    },
  });
}
