'use client';

import Link from 'next/link';
import { HealthIndicator } from '@/components/console/HealthIndicator';
import { Button } from '@/components/ui/button';

export function AppTopbar() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-sm">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className="hidden sm:inline">Internal ops console</span>
        <span className="hidden text-border sm:inline">|</span>
        <Link href="/" className="text-xs hover:text-foreground">
          Marketing hub
        </Link>
      </div>
      <div className="flex items-center gap-2">
        <HealthIndicator />
        <Button asChild variant="outline" size="sm">
          <Link href="/opt-out">Public opt-out</Link>
        </Button>
      </div>
    </header>
  );
}
