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
      <header>
        <Badge variant="outline">{brand.name}</Badge>
        <h1 className="mt-4 text-3xl font-bold">{headline}</h1>
        {comingSoon && <p className="mt-3 text-muted-foreground">We&apos;re launching soon</p>}
        {ctaLabel && (
          <div className="mt-6">
            <Button asChild>
              <Link href="/register">{ctaLabel}</Link>
            </Button>
          </div>
        )}
      </header>
    </article>
  );
}
