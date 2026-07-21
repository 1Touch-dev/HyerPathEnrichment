"use client";

import { useHealth } from "@/hooks/useHealth";
import { cn } from "@/src/lib/utils";

export function HealthIndicator() {
  const { online, loading } = useHealth();

  return (
    <div className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs">
      <span
        className={cn(
          "size-2 rounded-full",
          loading ? "bg-muted-foreground" : online ? "bg-emerald-500" : "bg-red-500",
        )}
        aria-hidden
      />
      <span className="text-muted-foreground">
        {loading ? "Checking…" : online ? "API online" : "Backend unreachable"}
      </span>
    </div>
  );
}
