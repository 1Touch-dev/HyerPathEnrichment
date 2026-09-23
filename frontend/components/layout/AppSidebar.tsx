"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { HyrepathLogo } from "@/components/layout/HyrepathLogo";
import { cn } from "@/src/lib/utils";
import { PRODUCT_ROOTS, type Product } from "@/src/lib/product-doors";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { toggleSidebar } from "@/store/slices/uiSlice";
import { SHELL_PRODUCT_META } from "./ShellPage";
import type { NavSection } from "./nav-config";

type AppSidebarProps = {
  product: Product;
  sections: NavSection[];
  matchesUnreadCount?: number;
};

const NAV_FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

const ACTIVE_NAV = "bg-primary-soft text-primary";
const IDLE_NAV = "text-muted-foreground hover:bg-surface-muted hover:text-foreground";

export function AppSidebar({ product, sections, matchesUnreadCount = 0 }: AppSidebarProps) {
  const pathname = usePathname();
  const dispatch = useAppDispatch();
  const sidebarOpen = useAppSelector((state) => state.ui.sidebarOpen);
  const meta = SHELL_PRODUCT_META[product];

  const isActive = (href: string) => {
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <aside
      data-shell-sidebar=""
      data-shell-product={product}
      className={cn(
        "flex h-full flex-col rounded-2xl border border-border/50 bg-surface shadow-float-sidebar transition-[width] duration-200",
        sidebarOpen ? "w-72" : "w-[78px]",
      )}
    >
      <div className="border-b border-border/60 px-3 py-4">
        {sidebarOpen ? (
          <div className="flex items-start justify-between gap-3">
            <Link
              href={PRODUCT_ROOTS[product]}
              aria-label="Hyrepath home"
              className={cn("flex min-w-0 flex-1 items-start gap-3 rounded-xl p-1", NAV_FOCUS)}
            >
              <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                <HyrepathLogo className="size-5" />
              </span>
              <span className="flex min-w-0 flex-col gap-1">
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                  Hyrepath
                </span>
                <span className="w-fit rounded-md bg-secondary px-2.5 py-1 text-sm font-medium leading-5 text-primary">
                  {meta.label}
                </span>
                <span className="text-xs text-subtle-foreground">{meta.description}</span>
              </span>
            </Link>
            <Button
              variant="ghost"
              size="icon"
              className="mt-1 h-8 w-8 shrink-0"
              onClick={() => dispatch(toggleSidebar())}
              aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            >
              {sidebarOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <Link
              href={PRODUCT_ROOTS[product]}
              aria-label="Hyrepath home"
              className={cn(
                "flex size-11 items-center justify-center rounded-2xl bg-primary-soft text-primary",
                NAV_FOCUS,
              )}
            >
              <HyrepathLogo className="size-5" />
            </Link>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={() => dispatch(toggleSidebar())}
              aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            >
              {sidebarOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </Button>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {sections.map((section, index) => (
          <div
            key={section.title}
            className={cn(index > 0 && "mt-5 border-t border-border/60 pt-5")}
          >
            {sidebarOpen ? (
              <p className="mb-2 px-3 text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
                {section.title}
              </p>
            ) : null}
            <ul className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                const showUnreadBadge = item.href === "/app/matches" && matchesUnreadCount > 0;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-label={item.label}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                        NAV_FOCUS,
                        active ? ACTIVE_NAV : IDLE_NAV,
                        !sidebarOpen && "justify-center px-0",
                      )}
                      title={!sidebarOpen ? item.label : undefined}
                    >
                      <span className="relative shrink-0">
                        <Icon className="h-4 w-4" aria-hidden="true" />
                        {showUnreadBadge && !sidebarOpen ? (
                          <span className="absolute -right-1 -top-1 size-2 rounded-full bg-destructive" />
                        ) : null}
                      </span>
                      {sidebarOpen ? <span>{item.label}</span> : null}
                      {showUnreadBadge && sidebarOpen ? (
                        <Badge variant="destructive" className="ml-auto px-1.5 py-0 text-[10px]">
                          {matchesUnreadCount}
                        </Badge>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-border/60 px-3 py-4">
        {sidebarOpen ? <p className="text-xs text-subtle-foreground">{meta.description}</p> : null}
      </div>
    </aside>
  );
}
