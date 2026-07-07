export const formatPercent = (value: number) => `${Math.round(value * 100)}%`;

export const tierLabels: Record<string, string> = {
  tier1: 'LinkedIn Photo',
  tier2: 'Username Discovery',
  tier3: 'Deep OSINT',
  tier4: 'Job & Business Intelligence',
};

export const initialsFrom = (value: string) =>
  value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');
