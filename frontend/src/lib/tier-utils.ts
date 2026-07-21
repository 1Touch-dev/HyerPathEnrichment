import { EnrichmentInput, RequestedTier } from "@/src/lib/types";
import { tierLabels } from "@/src/lib/utils";

export const ALL_TIERS: RequestedTier[] = ["tier1", "tier2", "tier3", "tier4"];

export type TierFieldRequirements = {
  linkedinUrl: boolean;
  username: boolean;
  emailOrCompanyOrUsername: boolean;
  businessOrJobSearch: boolean;
};

export type EnrichmentFieldValues = Pick<
  EnrichmentInput,
  "email" | "linkedinUrl" | "username" | "company" | "business" | "jobSearch"
>;

export function parseTiersFromQuery(value: string | null): RequestedTier[] {
  if (!value) {
    return [];
  }

  return value
    .split(",")
    .map((tier) => tier.trim())
    .filter(
      (tier): tier is RequestedTier =>
        tier === "tier1" || tier === "tier2" || tier === "tier3" || tier === "tier4",
    );
}

export function tiersToQuery(tiers: RequestedTier[]): string {
  return tiers.join(",");
}

export function getTierLabel(tier: RequestedTier): string {
  return tierLabels[tier] ?? tier;
}

export function availableTiersForMode(mode: "async" | "sync"): RequestedTier[] {
  if (mode === "sync") {
    return ALL_TIERS.filter((tier) => tier !== "tier1");
  }
  return ALL_TIERS;
}

export function normalizeTiersForMode(
  tiers: RequestedTier[],
  mode: "async" | "sync",
): RequestedTier[] {
  const allowed = new Set(availableTiersForMode(mode));
  return ALL_TIERS.filter((tier) => tiers.includes(tier) && allowed.has(tier));
}

export function hasValidTierSelection(tiers: RequestedTier[], mode: "async" | "sync"): boolean {
  return normalizeTiersForMode(tiers, mode).length > 0;
}

/** Flags matching backend EnrichmentRequest tier-specific identifier rules. */
export function tierFieldRequirements(tiers: RequestedTier[]): TierFieldRequirements {
  return {
    linkedinUrl: tiers.includes("tier1"),
    username: tiers.includes("tier2"),
    emailOrCompanyOrUsername: tiers.includes("tier3"),
    businessOrJobSearch: tiers.includes("tier4"),
  };
}

function hasValue(value: string | undefined): boolean {
  return Boolean(value?.trim());
}

/** True when field values satisfy backend rules for the selected tiers. */
export function isEnrichmentInputValidForTiers(
  fields: EnrichmentFieldValues,
  tiers: RequestedTier[],
): boolean {
  const requirements = tierFieldRequirements(tiers);

  if (requirements.linkedinUrl && !hasValue(fields.linkedinUrl)) {
    return false;
  }
  if (requirements.username && !hasValue(fields.username)) {
    return false;
  }
  if (
    requirements.emailOrCompanyOrUsername &&
    !hasValue(fields.username) &&
    !hasValue(fields.email) &&
    !hasValue(fields.company)
  ) {
    return false;
  }
  if (
    requirements.businessOrJobSearch &&
    !hasValue(fields.business) &&
    !hasValue(fields.jobSearch)
  ) {
    return false;
  }

  return true;
}
