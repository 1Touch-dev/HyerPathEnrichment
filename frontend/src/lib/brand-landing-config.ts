/** Reserved keys are never tier slugs, regardless of value type. */
const RESERVED_KEYS = new Set(["tiers", "headline", "cta_label", "_default"]);

export type BrandLandingCopy = {
  headline?: string;
  ctaLabel?: string;
};

export type ParsedBrandLandingConfig = {
  generalCopy: BrandLandingCopy | null;
  tiers: Record<string, BrandLandingCopy>;
};

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** A non-array object that has headline and/or cta_label. `{ body }` only is not copy. */
function isCopyObject(value: unknown): value is Record<string, unknown> {
  if (!isPlainObject(value)) return false;
  return typeof value.headline === "string" || typeof value.cta_label === "string";
}

function toCopy(value: Record<string, unknown>): BrandLandingCopy {
  const copy: BrandLandingCopy = {};
  if (typeof value.headline === "string") copy.headline = value.headline;
  if (typeof value.cta_label === "string") copy.ctaLabel = value.cta_label;
  return copy;
}

export function parseBrandLandingConfig(raw: unknown): ParsedBrandLandingConfig {
  if (!isPlainObject(raw)) {
    return { generalCopy: null, tiers: {} };
  }

  let generalCopy: BrandLandingCopy | null = null;
  if (isCopyObject(raw._default)) {
    generalCopy = toCopy(raw._default);
  } else if (isCopyObject(raw)) {
    generalCopy = toCopy(raw);
  }

  const tiers: Record<string, BrandLandingCopy> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (RESERVED_KEYS.has(key)) continue;
    if (isCopyObject(value)) {
      tiers[key] = toCopy(value);
    }
  }

  return { generalCopy, tiers };
}

export function isComingSoonConfig(parsed: ParsedBrandLandingConfig): boolean {
  return parsed.generalCopy === null;
}

/** Missing copy → caller must notFound(). Never fall back to general copy. */
export function getTierCopy(
  parsed: ParsedBrandLandingConfig,
  tier: string,
): BrandLandingCopy | null {
  if (RESERVED_KEYS.has(tier)) return null;
  return parsed.tiers[tier] ?? null;
}
