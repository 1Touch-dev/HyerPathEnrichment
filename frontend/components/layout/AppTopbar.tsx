"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HealthIndicator } from "@/components/console/HealthIndicator";
import { Button } from "@/components/ui/button";
import { HyrepathLogo } from "@/components/layout/HyrepathLogo";
import { UserMenu } from "@/components/auth/user-menu";
import type { Product } from "@/src/lib/product-doors";
import type { NavSection } from "./nav-config";

type AppTopbarProps = {
  product: Product;
  sections: NavSection[];
};

export function AppTopbar({ product, sections }: AppTopbarProps) {
  const pathname = usePathname();
  const activeItem = sections
    .flatMap((section) => section.items)
    .filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0];
  const sectionLabel =
    activeItem?.label ??
    (product === "candidate" ? "Candidate" : product === "desk" ? "Desk" : "Look up");
  const productLabel =
    product === "osint" ? "OSINT" : `${product[0].toUpperCase()}${product.slice(1)}`;
  const settingsHref = product === "osint" ? "/osint/settings" : "/app/settings";

  return (
    <header className="sticky top-0 z-50 flex h-16 shrink-0 items-center justify-between border-b border-border/40 bg-background/95 px-4 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/60 lg:px-6">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <HyrepathLogo className="size-5" />
          </div>
          <div>
            <p className="w-fit rounded-md bg-secondary px-2.5 py-1 text-sm font-medium leading-5 text-primary">
              {productLabel}
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
        <UserMenu settingsHref={settingsHref} />
      </div>
    </header>
  );
}
