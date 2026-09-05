"use client";

import Link from "next/link";
import { cn } from "@/src/lib/utils";
import { PRODUCT_ROOTS, type Product } from "@/src/lib/product-doors";
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
  return (
    <aside className="hidden h-full w-[72px] flex-col items-center justify-between border-r border-border bg-card py-4 md:flex lg:hidden">
      <div className="flex w-full flex-col items-center gap-4">
        <Link
          href={PRODUCT_ROOTS[product]}
          aria-label="Hyrepath home"
          className={cn(
            "flex size-10 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-primary",
            NAV_FOCUS,
          )}
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
                  aria-label={item.label}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex h-11 items-center justify-center rounded-md text-muted-foreground transition-colors",
                    NAV_FOCUS,
                    active ? "bg-secondary text-primary" : "hover:bg-muted hover:text-foreground",
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
      <p className="px-2 text-center text-[11px] leading-4 text-subtle-foreground">
        {product === "osint" ? "OSINT" : `${product[0].toUpperCase()}${product.slice(1)}`}
      </p>
    </aside>
  );
}
