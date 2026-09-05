import "server-only";
import { cache } from "react";
import { adaptPublicPortfolioProfile } from "@/src/lib/api-adapter";
import { unwrapEnvelopeData } from "@/src/lib/api-envelope";
import { backendFetchPublic } from "@/src/lib/backend-client";
import type { PublicPortfolioProfile } from "@/src/lib/types";

/** Deduped per-request fetch for public portfolio on /p. Missing/unpublished → null. */
export const fetchPublicPortfolio = cache(
  async (slug: string): Promise<PublicPortfolioProfile | null> => {
    const response = await backendFetchPublic(`/api/portfolio/public/${slug}`);
    if (!response.ok) return null;

    const raw = await response.json();
    return adaptPublicPortfolioProfile(unwrapEnvelopeData(raw));
  },
);
