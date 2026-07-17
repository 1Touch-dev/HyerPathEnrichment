import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LandingConfig, tierDescriptions } from '@/src/lib/landing-content';
import { tiersToQuery, getTierLabel } from '@/src/lib/tier-utils';
import { TrustBlock, SampleDossierCard } from '@/components/marketing/TrustBlock';

type LandingPageProps = {
  config: LandingConfig;
};

export function LandingPage({ config }: LandingPageProps) {
  const ctaHref = `/app/enrich?tiers=${tiersToQuery(config.tiers)}`;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-12 px-4 py-12">
      <section className="flex flex-col gap-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-brand-primary">{config.eyebrow}</p>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight">{config.headline}</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">{config.subheadline}</p>
        <ul className="flex flex-col gap-2 text-sm text-muted-foreground">
          {config.highlights.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="text-brand-secondary" aria-hidden>
                •
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <Button asChild className="w-fit">
          <Link href={ctaHref}>{config.ctaLabel}</Link>
        </Button>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold tracking-tight">Tier matrix</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {config.tiers.map((tier) => (
            <Card key={tier} className="border-border bg-card">
              <CardHeader>
                <Badge variant="secondary" className="w-fit font-mono">
                  {tier.toUpperCase()}
                </Badge>
                <CardTitle className="text-base">{getTierLabel(tier)}</CardTitle>
                <CardDescription>{tierDescriptions[tier]}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <SampleDossierCard audience={config.slug} />

      <TrustBlock />

      <section className="rounded-lg border border-brand-primary/25 bg-card p-6">
        <h2 className="text-xl font-semibold">Ready to run enrichment?</h2>
        <p className="mt-2 text-sm text-muted-foreground">Open the console with tiers pre-selected for your workflow.</p>
        <Button asChild className="mt-4">
          <Link href={ctaHref}>{config.ctaLabel}</Link>
        </Button>
      </section>
    </div>
  );
}
