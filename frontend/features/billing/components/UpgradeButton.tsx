"use client";

import { Button } from "@/components/ui/button";
import { useCheckout } from "../hooks/useSubscription";

interface UpgradeButtonProps {
  className?: string;
  size?: "default" | "sm" | "lg";
  variant?: "default" | "outline" | "secondary";
}

export function UpgradeButton({ className, size = "sm", variant = "default" }: UpgradeButtonProps) {
  const checkout = useCheckout();

  return (
    <Button
      className={className}
      size={size}
      variant={variant}
      onClick={() => checkout.mutate(undefined)}
      disabled={checkout.isPending}
    >
      {checkout.isPending ? "Redirecting..." : "Upgrade to Premium"}
    </Button>
  );
}
