import Link from "next/link";
import { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { HyrepathLogo } from "@/components/layout/HyrepathLogo";

type MarketingShellProps = {
  children: ReactNode;
};

export function MarketingShell({ children }: MarketingShellProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border/40 bg-gradient-to-b from-background to-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 lg:px-6">
          <Link href="/" className="group flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary transition-colors group-hover:bg-primary/20">
              <HyrepathLogo className="size-6" />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-xs font-bold uppercase tracking-widest text-primary">
                Hyrepath
              </span>
              <span className="text-base font-bold tracking-tight">Enrichment</span>
            </div>
          </Link>
          <div className="flex items-center gap-3">
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <Link href="/opt-out">Opt-out</Link>
            </Button>
            <Button asChild size="sm" className="shadow-sm">
              <Link href="/osint">Open console</Link>
            </Button>
          </div>
        </div>
      </header>
      <main>{children}</main>
      <footer className="border-t border-border bg-card/30">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-6 text-xs text-muted-foreground">
          <span>Self-hosted enrichment · LGPD / GDPR / CCPA</span>
          <div className="flex gap-4">
            <Link href="/opt-out" className="hover:text-primary">
              Opt-out
            </Link>
            <Link href="/osint" className="hover:text-primary">
              Console
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
