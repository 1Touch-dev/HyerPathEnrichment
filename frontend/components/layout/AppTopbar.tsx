"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HealthIndicator } from "@/components/console/HealthIndicator";
import { Button } from "@/components/ui/button";
import { HyrepathLogo } from "@/components/layout/HyrepathLogo";
import { UserMenu } from "@/components/auth/user-menu";

export function AppTopbar() {
  const pathname = usePathname();
  const sectionLabel = pathname.startsWith("/desk")
    ? "Desk"
    : pathname.startsWith("/app/history")
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
    <header className="sticky top-0 z-50 flex h-16 shrink-0 items-center justify-between border-b border-border/40 bg-background/95 px-4 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/60 lg:px-6">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <HyrepathLogo className="size-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Hyrepath
            </p>
            <p className="text-sm font-semibold">{sectionLabel}</p>
          </div>
        </div>
        <div className="hidden items-center gap-2 md:flex">
          <span className="text-muted-foreground">/</span>
          <Link
            href="/"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Marketing hub
          </Link>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <HealthIndicator />
        <Button asChild variant="outline" size="sm" className="h-9">
          <Link href="/opt-out">Opt out</Link>
        </Button>
        <UserMenu />
      </div>
    </header>
  );
}
