import { useQuery } from "@tanstack/react-query";
import { requestData } from "@/src/lib/api-client";

/**
 * Mirrors `backend/app/modules/demand_intelligence/schemas.py`'s `CountryTier` /
 * `CountryDemandRow` / `TopCountriesResponse` field-for-field (snake_case, as returned
 * by the backend) — the Next.js proxy route at
 * `app/api/demand-intelligence/top-countries/route.ts` passes the backend payload
 * through unchanged, so this hook exposes the raw snake_case shape rather than a
 * camelCase mapping.
 */
export type CountryTier = "tier_1" | "tier_2" | "tier_3";

export interface CountryDemandRow {
  country_iso2: string;
  role_bucket: string;
  posting_count: number;
  remote_posting_count: number;
  avg_salary_min: number | null;
  avg_salary_max: number | null;
  snapshot_date: string;
  tier: CountryTier;
}

export interface TopCountriesResponse {
  role: string;
  results: CountryDemandRow[];
  generated_at: string;
}

export const demandIntelligenceKeys = {
  all: ["demand-intelligence"] as const,
  topCountries: (role: string, limit: number) =>
    [...demandIntelligenceKeys.all, "top-countries", role, limit] as const,
};

/**
 * `GET /api/demand-intelligence/top-countries` — most-in-demand countries for a given
 * role query, tiered `tier_1`/`tier_2`/`tier_3` for recruiter sourcing prioritization.
 * `enabled` is gated on a non-empty, trimmed `role` so this never fires on an empty
 * search input.
 */
export function useTopCountriesForRole(role: string, limit: number = 10) {
  const trimmedRole = role.trim();

  return useQuery({
    queryKey: demandIntelligenceKeys.topCountries(trimmedRole, limit),
    queryFn: async () => {
      const params = new URLSearchParams({ role: trimmedRole, limit: String(limit) });
      return requestData<TopCountriesResponse>(
        `/api/demand-intelligence/top-countries?${params.toString()}`,
      );
    },
    enabled: trimmedRole.length > 0,
  });
}
