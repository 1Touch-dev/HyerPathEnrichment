"use client";

import { useState } from "react";
import Link from "next/link";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/src/lib/utils";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import type { NavSection } from "./nav-config";

type AppBottomNavProps = {
  sections: NavSection[];
  pathname: string;
  matchesUnreadCount?: number;
};

function isPathActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppBottomNav({ sections, pathname, matchesUnreadCount = 0 }: AppBottomNavProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const items = sections.flatMap((section) => section.items);
  const primaryItems = items.filter((item) => item.mobilePrimary).slice(0, 3);
  const primaryHrefs = new Set(primaryItems.map((item) => item.href));
  const moreItems = items.filter((item) => !primaryHrefs.has(item.href));
  const moreActive = moreItems.some((item) => isPathActive(pathname, item.href));

  return (
    <>
      <nav className="border-t border-border bg-card px-2 py-2 md:hidden">
        <ul
          className="grid gap-1"
          style={{ gridTemplateColumns: `repeat(${primaryItems.length + 1}, minmax(0, 1fr))` }}
        >
          {primaryItems.map((item) => {
            const Icon = item.icon;
            const active = isPathActive(pathname, item.href);
            const showUnreadBadge = item.href === "/app/matches" && matchesUnreadCount > 0;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "relative flex flex-col items-center gap-1 rounded-md px-2 py-2 text-xs",
                    active ? "bg-secondary text-primary" : "text-muted-foreground",
                  )}
                >
                  <span className="relative">
                    <Icon className="h-4 w-4" />
                    {showUnreadBadge ? (
                      <span className="absolute -right-1.5 -top-1.5 size-2 rounded-full bg-destructive" />
                    ) : null}
                  </span>
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
          <li>
            <button
              type="button"
              onClick={() => setMoreOpen(true)}
              className={cn(
                "flex w-full flex-col items-center gap-1 rounded-md px-2 py-2 text-xs",
                moreActive ? "bg-secondary text-primary" : "text-muted-foreground",
              )}
              aria-expanded={moreOpen}
              aria-haspopup="dialog"
            >
              <MoreHorizontal className="h-4 w-4" />
              <span>More</span>
            </button>
          </li>
        </ul>
      </nav>

      <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
        <SheetContent side="bottom" className="rounded-t-xl pb-8 md:hidden">
          <SheetHeader className="text-left">
            <SheetTitle>More</SheetTitle>
          </SheetHeader>
          <ul className="mt-4 space-y-1">
            {moreItems.map((item) => {
              const Icon = item.icon;
              const active = isPathActive(pathname, item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={() => setMoreOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-3 text-sm transition-colors",
                      active
                        ? "bg-secondary text-primary"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </SheetContent>
      </Sheet>
    </>
  );
}
