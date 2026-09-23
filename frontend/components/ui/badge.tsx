import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/src/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium tracking-[0.01em] transition-colors focus:outline-none focus:ring-4 focus:ring-ring/15 focus:ring-offset-0",
  {
    variants: {
      variant: {
        // Solid fills use *-foreground for contrast lock on primary/destructive.
        default: "border-transparent bg-primary text-primary-foreground shadow-sm",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        outline: "border-border bg-surface text-foreground",
        // Soft status chips (Done / Live / Needs review / Failed) — soft bg only, not row fills.
        success: "border-transparent bg-success-soft text-success",
        warning: "border-transparent bg-warning-soft text-warning",
        info: "border-transparent bg-info-soft text-info",
        destructive: "border-transparent bg-destructive-soft text-destructive",
        // Solid status variants when a stronger chip is needed.
        "success-solid": "border-transparent bg-success text-success-foreground shadow-sm",
        "warning-solid": "border-transparent bg-warning text-warning-foreground shadow-sm",
        "info-solid": "border-transparent bg-info text-info-foreground shadow-sm",
        "destructive-solid":
          "border-transparent bg-destructive text-destructive-foreground shadow-sm",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
