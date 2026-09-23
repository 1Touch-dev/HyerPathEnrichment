import Link from "next/link";
import { MarketingShell } from "@/components/layout/MarketingShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { hubAudiences } from "@/src/lib/landing-content";

/**
 * Public hub (`/`) — hero + use-case mosaic skinned to Figma `20 /`.
 * Structure and CTAs unchanged; violet primary CTAs with white text.
 */
export function HubPage() {
  return (
    <MarketingShell>
      <div className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-10 sm:py-14">
        <section className="flex flex-col gap-5 rounded-[1.5rem] border border-border/70 bg-surface p-6 shadow-panel sm:p-10">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
            Hyrepath Enrichment
          </p>
          <h1 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
            Customer-supplied identifiers → multi-tier public-signal dossier
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            Self-hosted enrichment pipeline with async queue, sync quick runs, and ops-grade trace.
            Pick an audience or open the console directly.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild className="w-full bg-primary text-primary-foreground sm:w-fit">
              <Link href="/osint">Open console</Link>
            </Button>
            <Button asChild variant="outline" className="w-full sm:w-fit">
              <Link href="/opt-out">Public opt-out</Link>
            </Button>
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <h2 className="text-2xl font-semibold tracking-tight">Pick your use case</h2>
            <p className="text-sm text-muted-foreground">
              One lookup flow. Different defaults per audience.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {hubAudiences.map((audience) => (
              <Card key={audience.slug} variant="accent" className="flex flex-col">
                <CardHeader className="pb-2">
                  <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
                    {audience.eyebrow}
                  </p>
                  <CardTitle className="text-base sm:text-lg">{audience.headline}</CardTitle>
                  <CardDescription className="font-mono text-xs uppercase tracking-wide">
                    {audience.tiers.map((tier) => tier.toUpperCase()).join(" · ")}
                  </CardDescription>
                </CardHeader>
                <CardContent className="mt-auto pt-0">
                  <Button asChild variant="outline" size="sm" className="w-full sm:w-fit">
                    <Link href={`/${audience.slug}`}>View landing</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </MarketingShell>
  );
}
