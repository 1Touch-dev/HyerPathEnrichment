import Link from 'next/link';
import { ReactNode } from 'react';
import { Button } from '@/components/ui/button';

type MarketingShellProps = {
  children: ReactNode;
};

export function MarketingShell({ children }: MarketingShellProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card/40">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link href="/" className="flex flex-col gap-0.5">
            <span className="text-xs font-semibold uppercase tracking-widest text-primary">Hyrepath</span>
            <span className="text-sm font-semibold tracking-tight">Enrichment</span>
          </Link>
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link href="/opt-out">Opt-out</Link>
            </Button>
            <Button asChild size="sm">
              <Link href="/app/enrich">Open console</Link>
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
            <Link href="/app/enrich" className="hover:text-primary">
              Console
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
