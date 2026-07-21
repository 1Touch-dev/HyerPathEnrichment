"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HealthIndicator } from "@/components/console/HealthIndicator";
import { Button } from "@/components/ui/button";

export function AppTopbar() {
  const pathname = usePathname();
  const sectionLabel = pathname.startsWith("/app/history")
    ? "History"
    : pathname.startsWith("/app/signals")
      ? "Signals"
      : pathname.startsWith("/app/dashboard")
        ? "Dashboard"
        : pathname.startsWith("/app/health")
          ? "Health"
          : pathname.startsWith("/app/settings")
            ? "Settings"
            : pathname.startsWith("/app/privacy")
              ? "Privacy"
              : pathname.startsWith("/app/jobs")
                ? "Profile"
                : "Look up";

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <div>
          <p className="text-xs text-muted-foreground">Hyrepath console</p>
          <p className="text-sm font-medium">{sectionLabel}</p>
        </div>
        <Link
          href="/"
          className="hidden text-xs text-muted-foreground hover:text-foreground sm:inline"
        >
          Marketing hub
        </Link>
      </div>
      <div className="flex items-center gap-2">
        <HealthIndicator />
        <Button asChild variant="outline" size="sm">
          <Link href="/opt-out">Opt out</Link>
        </Button>
      </div>
    </header>
  );
}
