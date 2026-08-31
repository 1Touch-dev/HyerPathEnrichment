import "server-only";
import { cache } from "react";
import { adaptPublicBrand } from "@/src/lib/api-adapter";
import { unwrapEnvelopeData } from "@/src/lib/api-envelope";
import { backendFetchPublic } from "@/src/lib/backend-client";
import type { PublicBrand } from "@/src/lib/types";

/** Deduped per-request fetch for public brand landings. Missing/inactive → null. */
export const fetchPublicBrand = cache(async (slug: string): Promise<PublicBrand | null> => {
  const response = await backendFetchPublic(`/api/brands/public/${slug}`);
  if (!response.ok) return null;

  const raw = await response.json();
  return adaptPublicBrand(unwrapEnvelopeData(raw));
});
