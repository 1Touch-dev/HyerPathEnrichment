import Link from 'next/link';
import { MarketingShell } from '@/components/layout/MarketingShell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { hubAudiences } from '@/src/lib/landing-content';
import { getTierLabel } from '@/src/lib/tier-utils';

export default function HubPage() {
  return (
    <MarketingShell>
      <div className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-12">
        <section className="flex flex-col gap-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-brand-primary">Hyrepath Enrichment</p>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight">
            Customer-supplied identifiers → multi-tier public-signal dossier
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Self-hosted enrichment pipeline with async queue, sync quick runs, and ops-grade trace. Pick an audience or
            open the console directly.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild className="w-fit">
              <Link href="/app">Open console</Link>
            </Button>
            <Button asChild variant="outline" className="w-fit">
              <Link href="/opt-out">Public opt-out</Link>
            </Button>
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {hubAudiences.map((audience) => (
            <Card key={audience.slug} className="border-border bg-card">
              <CardHeader>
                <p className="text-xs font-semibold uppercase tracking-widest text-brand-tertiary">{audience.eyebrow}</p>
                <CardTitle className="text-lg">{audience.headline}</CardTitle>
                <CardDescription className="font-mono text-xs">
                  {audience.tiers.map((t) => getTierLabel(t)).join(' · ')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button asChild variant="outline" size="sm">
                  <Link href={`/${audience.slug}`}>View landing</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </section>
      </div>
    </MarketingShell>
  );
}
