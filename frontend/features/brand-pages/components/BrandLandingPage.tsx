import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  isComingSoonConfig,
  parseBrandLandingConfig,
  type BrandLandingCopy,
} from "@/src/lib/brand-landing-config";
import type { PublicBrand } from "@/src/lib/types";

interface BrandLandingPageProps {
  brand: PublicBrand;
  /** When set (tier page), overrides headline/CTA only. Never fall back to general copy. */
  tierConfig?: BrandLandingCopy;
}

export function BrandLandingPage({ brand, tierConfig }: BrandLandingPageProps) {
  const parsed = parseBrandLandingConfig(brand.landingPageTierConfig);
  const comingSoon = tierConfig === undefined && isComingSoonConfig(parsed);
  const copy = tierConfig ?? parsed.generalCopy;
  const headline = comingSoon ? brand.name : (copy?.headline ?? brand.name);
  const ctaLabel = comingSoon ? "Get started" : copy?.ctaLabel;

  return (
    <article className="mx-auto max-w-2xl space-y-8 px-4 py-12">
      <header className="space-y-4 rounded-[1.5rem] border border-border/70 bg-card p-6 shadow-panel sm:p-10">
        <Badge variant="secondary" className="bg-primary-soft text-primary">
          {brand.name}
        </Badge>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">{headline}</h1>
        {comingSoon && <p className="text-muted-foreground">We&apos;re launching soon</p>}
        {ctaLabel && (
          <div className="pt-2">
            <Button asChild>
              <Link href="/register">{ctaLabel}</Link>
            </Button>
          </div>
        )}
      </header>
    </article>
  );
}
