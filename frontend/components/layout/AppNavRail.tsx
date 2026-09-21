"use client";

import Link from "next/link";
import { HyrepathLogo } from "@/components/layout/HyrepathLogo";
import { cn } from "@/src/lib/utils";
import { PRODUCT_ROOTS, type Product } from "@/src/lib/product-doors";
import { SHELL_PRODUCT_META } from "./ShellPage";
import type { NavSection } from "./nav-config";

const NAV_FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

type AppNavRailProps = {
  product: Product;
  sections: NavSection[];
  pathname: string;
  matchesUnreadCount?: number;
};

export function AppNavRail({
  product,
  sections,
  pathname,
  matchesUnreadCount = 0,
}: AppNavRailProps) {
  const meta = SHELL_PRODUCT_META[product];

  return (
    <aside
      data-shell-nav-rail=""
      data-shell-product={product}
      className="hidden h-full w-[84px] flex-col items-center justify-between border-r border-border/70 bg-surface-elevated/80 px-2 py-4 shadow-panel backdrop-blur supports-[backdrop-filter]:bg-surface-elevated/70 md:flex lg:hidden"
    >
      <div className="flex w-full flex-col items-center gap-4">
        <Link
          href={PRODUCT_ROOTS[product]}
          aria-label="Hyrepath home"
          className={cn(
            "flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm",
            NAV_FOCUS,
          )}
        >
          <HyrepathLogo className="size-5" />
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
                  aria-label={item.label}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex h-12 items-center justify-center rounded-xl text-muted-foreground transition-colors",
                    NAV_FOCUS,
                    active
                      ? "border border-border/70 bg-secondary/90 text-primary shadow-sm"
                      : "hover:bg-surface-muted hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {showUnreadBadge ? (
                    <span className="absolute right-3 top-2 size-2 rounded-full bg-destructive" />
                  ) : null}
                </Link>
              );
            })}
        </nav>
      </div>
      <p className="px-2 text-center text-[11px] font-medium leading-4 text-subtle-foreground">
        {meta.label}
      </p>
    </aside>
  );
}
