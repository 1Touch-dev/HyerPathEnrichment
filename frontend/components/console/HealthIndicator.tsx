"use client";

import { useHealth } from "@/hooks/useHealth";
import { cn } from "@/src/lib/utils";

export function HealthIndicator() {
  const { online, loading } = useHealth();

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-surface px-3 py-2 text-xs shadow-sm">
      <span
        className={cn(
          "relative size-2 rounded-full",
          loading ? "bg-muted-foreground" : online ? "bg-emerald-500" : "bg-red-500",
        )}
        aria-hidden
      >
        {online && !loading && (
          <span className="absolute inset-0 size-2 animate-ping rounded-full bg-emerald-500 opacity-75" />
        )}
      </span>
      <span className="font-medium text-foreground">
        {loading ? "Checking connectivity" : online ? "API online" : "API offline"}
      </span>
    </div>
  );
}
