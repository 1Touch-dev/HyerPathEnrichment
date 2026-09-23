import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SampleDossierCard, TrustBlock } from "@/components/marketing/TrustBlock";
import type { LandingConfig } from "@/src/lib/landing-content";
import { tiersToQuery } from "@/src/lib/tier-utils";

type PersonaLandingPageProps = {
  config: LandingConfig;
};

/**
 * Audience landing skin (Figma `20 /{persona}`) — white surfaces + violet CTAs.
 * Fields, tiers, and CTA targets unchanged from the prior landing.
 */
export function PersonaLandingPage({ config }: PersonaLandingPageProps) {
  const ctaHref = `/osint?tiers=${tiersToQuery(config.tiers)}`;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-10 sm:gap-12 sm:py-14">
      <section className="flex flex-col gap-5 rounded-[1.5rem] border border-border/70 bg-surface p-6 shadow-panel sm:p-10">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
          {config.eyebrow}
        </p>
        <h1 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
          {config.headline}
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
          {config.subheadline}
        </p>
        <ul className="flex flex-col gap-2 text-sm text-muted-foreground">
          {config.highlights.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="font-semibold text-primary" aria-hidden>
                •
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <Button asChild className="w-full bg-primary text-primary-foreground sm:w-fit">
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
          These tiers are pre-selected for your audience. You can adjust them after you open the
          console.
        </p>
      </section>

      <SampleDossierCard audience={config.slug} />

      <TrustBlock />

      <Card variant="accent" className="p-0">
        <CardHeader>
          <CardTitle className="text-xl">Ready to run enrichment?</CardTitle>
          <CardDescription>
            Open the console with tiers pre-selected for your workflow.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild className="bg-primary text-primary-foreground">
            <Link href={ctaHref}>{config.ctaLabel}</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
