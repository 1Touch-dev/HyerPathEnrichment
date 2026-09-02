"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/src/lib/utils";
import { PRODUCT_ROOTS, type Product } from "@/src/lib/product-doors";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { toggleSidebar } from "@/store/slices/uiSlice";
import type { NavSection } from "./nav-config";

type AppSidebarProps = {
  product: Product;
  sections: NavSection[];
  matchesUnreadCount?: number;
};

const PRODUCT_DESCRIPTION: Record<Product, string> = {
  candidate: "Candidate workspace",
  desk: "Staff operations",
  osint: "Public-only lookup",
};

export function AppSidebar({ product, sections, matchesUnreadCount = 0 }: AppSidebarProps) {
  const pathname = usePathname();
  const dispatch = useAppDispatch();
  const sidebarOpen = useAppSelector((state) => state.ui.sidebarOpen);

  const isActive = (href: string) => {
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-border bg-card transition-all duration-200",
        sidebarOpen ? "w-60" : "w-16",
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-4">
        {sidebarOpen ? (
          <Link href={PRODUCT_ROOTS[product]} className="flex flex-col items-start gap-1 px-1">
            <span className="text-sm font-semibold tracking-tight text-primary">Hyrepath</span>
            <span className="rounded-md bg-secondary px-2.5 py-1 text-sm font-medium leading-5 text-primary">
              {product === "osint" ? "OSINT" : `${product[0].toUpperCase()}${product.slice(1)}`}
            </span>
          </Link>
        ) : (
          <Link href={PRODUCT_ROOTS[product]} className="mx-auto text-xs font-bold text-primary">
            H
          </Link>
        )}
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

      <nav className="flex-1 space-y-6 overflow-y-auto px-2 py-4">
        {sections.map((section) => (
          <div key={section.title}>
            {sidebarOpen ? (
              <p className="mb-2 px-2 text-xs font-medium text-muted-foreground">{section.title}</p>
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
                      className={cn(
                        "flex items-center gap-3 rounded-md px-2 py-2 text-sm transition-colors",
                        active
                          ? "bg-secondary text-primary"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground",
                        !sidebarOpen && "justify-center px-0",
                      )}
                      title={!sidebarOpen ? item.label : undefined}
                    >
                      <span className="relative shrink-0">
                        <Icon className="h-4 w-4" />
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

      <div className="border-t border-border px-3 py-4">
        {sidebarOpen ? (
          <p className="text-xs text-subtle-foreground">{PRODUCT_DESCRIPTION[product]}</p>
        ) : null}
      </div>
    </aside>
  );
}
