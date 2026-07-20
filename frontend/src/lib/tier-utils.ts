import { RequestedTier } from '@/src/lib/types';
import { tierLabels } from '@/src/lib/utils';

export const ALL_TIERS: RequestedTier[] = ['tier1', 'tier2', 'tier3', 'tier4'];

export type DepthPreset = 'quick' | 'standard' | 'deep';

export const DEPTH_PRESETS: Record<DepthPreset, RequestedTier[]> = {
  // Quick: username discovery + lightweight correlation.
  quick: ['tier2'],
  // Standard: the most common workflow for many OSINT tasks.
  standard: ['tier2', 'tier3'],
  // Deep: full dossier with browser pipeline (when allowed) + job intelligence.
  deep: ['tier1', 'tier2', 'tier3', 'tier4'],
};

export function parseTiersFromQuery(value: string | null): RequestedTier[] {
  if (!value) {
    return [];
  }

  return value
    .split(',')
    .map((tier) => tier.trim())
    .filter((tier): tier is RequestedTier =>
      tier === 'tier1' || tier === 'tier2' || tier === 'tier3' || tier === 'tier4',
    );
}

export function tiersToQuery(tiers: RequestedTier[]): string {
  return tiers.join(',');
}

export function getTierLabel(tier: RequestedTier): string {
  return tierLabels[tier] ?? tier;
}

export function availableTiersForMode(mode: 'async' | 'sync'): RequestedTier[] {
  if (mode === 'sync') {
    return ALL_TIERS.filter((tier) => tier !== 'tier1');
  }
  return ALL_TIERS;
}

export function hasValidTierSelection(tiers: RequestedTier[], mode: 'async' | 'sync'): boolean {
  const allowed = availableTiersForMode(mode);
  return tiers.some((tier) => allowed.includes(tier));
}

export function getTiersFromDepthPreset(preset: DepthPreset, mode: 'async' | 'sync'): RequestedTier[] {
  const allowed = new Set(availableTiersForMode(mode));
  return DEPTH_PRESETS[preset].filter((tier) => allowed.has(tier));
}

export function inferDepthPresetFromTiers(tiers: RequestedTier[], mode: 'async' | 'sync'): DepthPreset {
  const selected = new Set(availableTiersForMode(mode).filter((tier) => tiers.includes(tier)));
  for (const [preset, presetTiers] of Object.entries(DEPTH_PRESETS) as Array<[DepthPreset, RequestedTier[]]>) {
    const required = new Set(presetTiers.filter((t) => availableTiersForMode(mode).includes(t)));
    const matches =
      selected.size === required.size && Array.from(selected).every((t) => required.has(t));
    if (matches) return preset;
  }
  return 'standard';
}
