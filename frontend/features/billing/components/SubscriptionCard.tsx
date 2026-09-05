"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useBillingPortal, useCheckout, useSubscription } from "../hooks/useSubscription";

function formatPeriodEnd(value: string | null): string | null {
  if (!value) return null;
  try {
    return new Date(value).toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return null;
  }
}

export function SubscriptionCard() {
  const { data: subscription, isLoading, isError } = useSubscription();
  const checkout = useCheckout();
  const portal = useBillingPortal();

  const isPremium = subscription?.effectiveTier === "premium";
  const renewal = formatPeriodEnd(subscription?.currentPeriodEnd ?? null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Subscription</CardTitle>
        <CardDescription>Manage your premium access to enriched job insights.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 max-w-md">
        {isLoading ? (
          <div className="h-16 animate-pulse rounded-md bg-muted" />
        ) : isError ? (
          <p className="text-sm text-muted-foreground">
            Subscription status is unavailable right now.
          </p>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Plan</span>
              <Badge variant={isPremium ? "default" : "secondary"}>
                {isPremium ? "Premium" : "Free preview"}
              </Badge>
            </div>
            {subscription?.status && subscription.status !== "none" ? (
              <p className="text-sm text-muted-foreground capitalize">
                Status: {subscription.status.replace("_", " ")}
              </p>
            ) : null}
            {renewal ? <p className="text-sm text-muted-foreground">Renews on {renewal}</p> : null}
            {!isPremium ? (
              <p className="text-sm text-muted-foreground">
                Free accounts see blurred match insights. Upgrade for full AI explanations and CV
                feedback details.
              </p>
            ) : null}
          </>
        )}

        <div className="flex flex-wrap gap-2">
          {!isPremium ? (
            <Button onClick={() => checkout.mutate(undefined)} disabled={checkout.isPending}>
              {checkout.isPending ? "Redirecting..." : "Upgrade"}
            </Button>
          ) : subscription?.stripeCustomerId ? (
            <Button
              variant="outline"
              onClick={() => portal.mutate(undefined)}
              disabled={portal.isPending}
            >
              {portal.isPending ? "Opening..." : "Manage billing"}
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
