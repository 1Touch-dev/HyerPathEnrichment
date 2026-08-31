/** Reserved keys are never tier slugs, regardless of value type. */
export const RESERVED_KEYS = new Set(["tiers", "headline", "cta_label", "_default"]);

const TIER_SLUG_PATTERN = /^[a-z0-9-]+$/;

export type BrandLandingCopy = {
  headline?: string;
  ctaLabel?: string;
};

export type ParsedBrandLandingConfig = {
  generalCopy: BrandLandingCopy | null;
  tiers: Record<string, BrandLandingCopy>;
};

export type SerializeBrandLandingResult =
  { ok: true; value: Record<string, unknown> | null | undefined } | { ok: false; error: string };

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

function trimCopy(copy: BrandLandingCopy | null): BrandLandingCopy | null {
  if (!copy) return null;
  const headline = copy.headline?.trim();
  const ctaLabel = copy.ctaLabel?.trim();
  const out: BrandLandingCopy = {};
  if (headline) out.headline = headline;
  if (ctaLabel) out.ctaLabel = ctaLabel;
  return out.headline || out.ctaLabel ? out : null;
}

function copyToWire(copy: BrandLandingCopy): {
  headline?: string;
  cta_label?: string;
} {
  const out: { headline?: string; cta_label?: string } = {};
  if (copy.headline) out.headline = copy.headline;
  if (copy.ctaLabel) out.cta_label = copy.ctaLabel;
  return out;
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

/**
 * Wire-format map: optional top-level headline / cta_label plus non-reserved
 * slug keys. Never emits `tiers`, `_default`, or reserved keys as tier slugs.
 */
export function serializeBrandLandingConfig(
  parsed: ParsedBrandLandingConfig,
  options: { previousWasObject: boolean; isCreate: boolean },
): SerializeBrandLandingResult {
  const value: Record<string, unknown> = {};

  const general = trimCopy(parsed.generalCopy);
  if (general) {
    const wire = copyToWire(general);
    if (wire.headline) value.headline = wire.headline;
    if (wire.cta_label) value.cta_label = wire.cta_label;
  }

  for (const [slug, copy] of Object.entries(parsed.tiers)) {
    if (RESERVED_KEYS.has(slug)) {
      return {
        ok: false,
        error: `"${slug}" is a reserved key and cannot be a tier slug`,
      };
    }
    if (!TIER_SLUG_PATTERN.test(slug)) {
      return {
        ok: false,
        error: `Tier slug "${slug}" must match ^[a-z0-9-]+$`,
      };
    }
    const trimmed = trimCopy(copy);
    if (!trimmed) continue;
    value[slug] = copyToWire(trimmed);
  }

  if (Object.keys(value).length === 0) {
    if (options.isCreate || !options.previousWasObject) {
      return { ok: true, value: undefined };
    }
    return { ok: true, value: null };
  }

  return { ok: true, value };
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
