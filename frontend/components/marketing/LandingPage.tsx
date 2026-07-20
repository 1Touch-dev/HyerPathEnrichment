import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LandingConfig } from '@/src/lib/landing-content';
import { tiersToQuery } from '@/src/lib/tier-utils';
import { TrustBlock, SampleDossierCard } from '@/components/marketing/TrustBlock';

type LandingPageProps = {
  config: LandingConfig;
};

export function LandingPage({ config }: LandingPageProps) {
  const ctaHref = `/app/enrich?tiers=${tiersToQuery(config.tiers)}`;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-12 px-4 py-12">
      <section className="flex flex-col gap-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">{config.eyebrow}</p>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight">{config.headline}</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">{config.subheadline}</p>
        <ul className="flex flex-col gap-2 text-sm text-muted-foreground">
          {config.highlights.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="text-primary" aria-hidden>
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
        <h2 className="text-2xl font-semibold tracking-tight">Default depth</h2>
        <div className="flex flex-wrap gap-2">
          {config.tiers.map((tier) => (
            <Badge key={tier} variant="outline" className="font-mono">
              {tier.toUpperCase()}
            </Badge>
          ))}
        </div>
        <p className="text-sm text-muted-foreground">
          These tiers are pre-selected for your audience. You can adjust them after you open the console.
        </p>
      </section>

      <SampleDossierCard audience={config.slug} />

      <TrustBlock />

      <section className="rounded-lg border border-primary/25 bg-card p-6">
        <h2 className="text-xl font-semibold">Ready to run enrichment?</h2>
        <p className="mt-2 text-sm text-muted-foreground">Open the console with tiers pre-selected for your workflow.</p>
        <Button asChild className="mt-4">
          <Link href={ctaHref}>{config.ctaLabel}</Link>
        </Button>
      </section>
    </div>
  );
}
