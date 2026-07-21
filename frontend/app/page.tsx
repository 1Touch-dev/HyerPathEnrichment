import Link from "next/link";
import { MarketingShell } from "@/components/layout/MarketingShell";
import { Button } from "@/components/ui/button";
import { hubAudiences } from "@/src/lib/landing-content";

export default function HubPage() {
  return (
    <MarketingShell>
      <div className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-12">
        <section className="flex flex-col gap-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">
            Hyrepath Enrichment
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight">
            Customer-supplied identifiers → multi-tier public-signal dossier
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Self-hosted enrichment pipeline with async queue, sync quick runs, and ops-grade trace.
            Pick an audience or open the console directly.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild className="w-fit">
              <Link href="/app/enrich">Open console</Link>
            </Button>
            <Button asChild variant="outline" className="w-fit">
              <Link href="/opt-out">Public opt-out</Link>
            </Button>
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-2xl font-semibold tracking-tight">Pick your use case</h2>
          <p className="text-sm text-muted-foreground">
            One lookup flow. Different defaults per audience.
          </p>

          <div className="flex flex-col gap-2">
            {hubAudiences.map((audience) => (
              <div
                key={audience.slug}
                className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-widest text-primary">
                    {audience.eyebrow}
                  </p>
                  <p className="mt-1 truncate text-sm font-medium">{audience.headline}</p>
                </div>
                <Button asChild variant="outline" size="sm">
                  <Link href={`/${audience.slug}`}>View landing</Link>
                </Button>
              </div>
            ))}
          </div>
        </section>
      </div>
    </MarketingShell>
  );
}
