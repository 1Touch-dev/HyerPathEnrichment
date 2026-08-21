"use client";

import Link from "next/link";
import { cn } from "@/src/lib/utils";
import { adminNav, allNavSections } from "./nav-config";

type AppNavRailProps = {
  pathname: string;
  matchesUnreadCount?: number;
  isAdmin?: boolean;
};

export function AppNavRail({ pathname, matchesUnreadCount = 0, isAdmin = false }: AppNavRailProps) {
  const sections = isAdmin ? [...allNavSections, adminNav] : allNavSections;

  return (
    <aside className="hidden h-full w-[72px] flex-col items-center justify-between border-r border-border bg-card py-4 md:flex lg:hidden">
      <div className="flex w-full flex-col items-center gap-4">
        <Link
          href="/app/enrich"
          className="flex size-10 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-primary"
        >
          H
        </Link>
        <nav className="flex w-full flex-col gap-2 px-2">
          {sections
            .flatMap((section) => section.items)
            .map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              const showUnreadBadge = item.href === "/app/matches" && matchesUnreadCount > 0;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  title={item.label}
                  className={cn(
                    "relative flex h-11 items-center justify-center rounded-md text-muted-foreground transition-colors",
                    active ? "bg-secondary text-primary" : "hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {showUnreadBadge ? (
                    <span className="absolute right-3 top-2 size-2 rounded-full bg-destructive" />
                  ) : null}
                </Link>
              );
            })}
        </nav>
      </div>
      <p className="px-2 text-center text-[11px] leading-4 text-subtle-foreground">
        Public-only lookup
      </p>
    </aside>
  );
}
