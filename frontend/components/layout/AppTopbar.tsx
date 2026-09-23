"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HealthIndicator } from "@/components/console/HealthIndicator";
import { Button } from "@/components/ui/button";
import { HyrepathLogo } from "@/components/layout/HyrepathLogo";
import { UserMenu } from "@/components/auth/user-menu";
import { PRODUCT_ROOTS, type Product } from "@/src/lib/product-doors";
import { SHELL_PRODUCT_META } from "./ShellPage";
import type { NavSection } from "./nav-config";

type AppTopbarProps = {
  product: Product;
  sections: NavSection[];
};

export function AppTopbar({ product, sections }: AppTopbarProps) {
  const pathname = usePathname();
  const meta = SHELL_PRODUCT_META[product];
  const activeItem = sections
    .flatMap((section) => section.items)
    .filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0];
  const sectionLabel =
    activeItem?.label ??
    (product === "candidate" ? "Candidate" : product === "desk" ? "Desk" : "Look up");
  const settingsHref = product === "osint" ? "/osint/settings" : "/app/settings";

  return (
    <header
      data-shell-topbar=""
      data-shell-product={product}
      className="sticky top-0 z-50 flex h-16 shrink-0 items-center justify-between border-b border-border/50 bg-surface/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-surface/80 lg:px-6"
    >
      <div className="flex min-w-0 items-center gap-3 sm:gap-4">
        <Link
          href={PRODUCT_ROOTS[product]}
          aria-label={`${meta.label} home`}
          className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary transition-colors hover:bg-primary-soft/80 lg:hidden"
        >
          <div className="flex size-8 items-center justify-center rounded-lg">
            <HyrepathLogo className="size-5" />
          </div>
        </Link>
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <p className="w-fit rounded-md bg-secondary px-2.5 py-1 text-sm font-medium leading-5 text-primary">
              {meta.label}
            </p>
            <p className="hidden text-xs text-subtle-foreground sm:inline">{meta.description}</p>
          </div>
          <div className="flex min-w-0 items-center gap-2">
            <p className="truncate text-sm font-semibold">{sectionLabel}</p>
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
        </div>
      </div>
      <div className="flex items-center gap-2 sm:gap-3">
        <HealthIndicator />
        <Button asChild variant="outline" size="sm" className="h-9">
          <Link href="/opt-out">Opt out</Link>
        </Button>
        <UserMenu settingsHref={settingsHref} />
      </div>
    </header>
  );
}
