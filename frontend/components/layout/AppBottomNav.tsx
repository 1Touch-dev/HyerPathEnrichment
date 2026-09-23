"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/src/lib/utils";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import type { NavSection } from "./nav-config";

const NAV_FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

const ACTIVE_NAV = "bg-primary-soft text-primary";
const IDLE_NAV = "text-muted-foreground hover:bg-surface-muted hover:text-foreground";

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
  const moreTriggerRef = useRef<HTMLButtonElement>(null);
  const items = sections.flatMap((section) => section.items);
  const primaryItems = items.filter((item) => item.mobilePrimary).slice(0, 3);
  const primaryHrefs = new Set(primaryItems.map((item) => item.href));
  const moreItems = items.filter((item) => !primaryHrefs.has(item.href));
  const moreActive = moreItems.some((item) => isPathActive(pathname, item.href));

  return (
    <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
      <nav className="border-t border-border/50 bg-surface/95 px-3 py-2.5 backdrop-blur supports-[backdrop-filter]:bg-surface/80 md:hidden">
        <ul
          className="mx-auto grid max-w-xl gap-1 rounded-2xl border border-border/50 bg-surface p-1.5 shadow-panel"
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
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex min-h-11 flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-xs transition-colors",
                    NAV_FOCUS,
                    active ? ACTIVE_NAV : IDLE_NAV,
                  )}
                >
                  <span className="relative">
                    <Icon className="h-4 w-4" aria-hidden="true" />
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
            <SheetTrigger asChild>
              <button
                ref={moreTriggerRef}
                type="button"
                className={cn(
                  "flex min-h-11 w-full flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-xs transition-colors",
                  NAV_FOCUS,
                  moreActive ? ACTIVE_NAV : IDLE_NAV,
                )}
                aria-expanded={moreOpen}
              >
                <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                <span>More</span>
              </button>
            </SheetTrigger>
          </li>
        </ul>
      </nav>

      <SheetContent
        side="bottom"
        className="rounded-t-[1.75rem] border-border/50 bg-surface px-4 pb-8 shadow-overlay md:hidden"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          moreTriggerRef.current?.focus();
        }}
      >
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
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex min-h-11 items-center gap-3 rounded-xl px-3 py-3 text-sm transition-colors",
                    NAV_FOCUS,
                    active ? ACTIVE_NAV : IDLE_NAV,
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </SheetContent>
    </Sheet>
  );
}
