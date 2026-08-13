import "server-only";

/**
 * Bridge between the real backend portfolio schemas
 * (`backend/app/modules/portfolio/schemas.py`) and the shapes the shared,
 * do-not-edit `src/lib/api-adapter.ts` placeholder adapters
 * (`adaptPortfolioProfile`, `adaptPublicPortfolioProfile`) expect.
 *
 * Real backend uses `display_name`/`headline`/`bio` and
 * `item_type: "github" | "live_demo" | "case_study" | "other"`.
 * The shared adapter's hand-declared `Raw*Response` placeholders (written
 * before the backend module existed) use `headline`/`summary` and
 * `item_type: "github_repo" | "live_demo" | "case_study" | "other_link"`.
 * `display_name` has no frontend-facing equivalent yet.
 *
 * This file lives under `features/portfolio/` (server-only) rather than in
 * `src/lib/api-adapter.ts` so the mismatch is isolated to this feature's own
 * server-side boundary (BFF routes + the public `/p/[slug]` server component
 * page) instead of being duplicated as ad-hoc inline code in each call site,
 * without editing the shared, do-not-touch adapter file.
 */

export type BackendItemType = "github" | "live_demo" | "case_study" | "other";
export type FrontendItemType = "github_repo" | "live_demo" | "case_study" | "other_link";

const ITEM_TYPE_FROM_BACKEND: Record<BackendItemType, FrontendItemType> = {
  github: "github_repo",
  live_demo: "live_demo",
  case_study: "case_study",
  other: "other_link",
};

const ITEM_TYPE_TO_BACKEND: Record<FrontendItemType, BackendItemType> = {
  github_repo: "github",
  live_demo: "live_demo",
  case_study: "case_study",
  other_link: "other",
};

export function itemTypeFromBackend(value: string): FrontendItemType {
  return ITEM_TYPE_FROM_BACKEND[value as BackendItemType] ?? "other_link";
}

export function itemTypeToBackend(value: string): BackendItemType {
  return ITEM_TYPE_TO_BACKEND[value as FrontendItemType] ?? "other";
}

export interface BackendPortfolioItem {
  item_id: string;
  item_type: string;
  title: string;
  description: string | null;
  url: string;
  display_order: number;
  created_at: string;
}

export interface BackendPortfolioProfile {
  profile_id: string;
  user_id: string;
  slug: string;
  display_name: string | null;
  headline: string | null;
  bio: string | null;
  is_published: boolean;
  public_url: string;
  items: BackendPortfolioItem[];
  created_at: string;
  updated_at: string;
}

export interface BackendPublicPortfolioProfile {
  slug: string;
  display_name: string | null;
  headline: string | null;
  bio: string | null;
  items: BackendPortfolioItem[];
}

function toRawItem(item: BackendPortfolioItem) {
  return {
    item_id: item.item_id,
    item_type: itemTypeFromBackend(item.item_type),
    title: item.title,
    description: item.description,
    url: item.url,
    display_order: item.display_order,
  };
}

/** Shape matching api-adapter.ts's (unexported) `RawPortfolioProfileResponse`. */
export function toRawPortfolioProfile(raw: BackendPortfolioProfile) {
  return {
    profile_id: raw.profile_id,
    slug: raw.slug,
    headline: raw.headline,
    summary: raw.bio,
    is_published: raw.is_published,
    items: raw.items.map(toRawItem),
    created_at: raw.created_at,
    updated_at: raw.updated_at,
  };
}

/** Shape matching api-adapter.ts's (unexported) `RawPublicPortfolioProfileResponse`. */
export function toRawPublicPortfolioProfile(raw: BackendPublicPortfolioProfile) {
  return {
    slug: raw.slug,
    headline: raw.headline,
    summary: raw.bio,
    items: raw.items.map(toRawItem),
  };
}

/** Shape matching api-adapter.ts's (unexported) `RawPortfolioItemResponse`. */
export function toRawPortfolioItem(raw: BackendPortfolioItem) {
  return toRawItem(raw);
}

/**
 * Full camelCase adaptation for a single item (api-adapter.ts's own
 * `adaptPortfolioItem` is not exported, so it can't be reused directly here —
 * this mirrors it exactly for the one route, §11.5's POST /api/portfolio/items,
 * that returns a bare item rather than a full profile).
 */
export function adaptBackendPortfolioItem(raw: BackendPortfolioItem) {
  return {
    itemId: raw.item_id,
    itemType: itemTypeFromBackend(raw.item_type),
    title: raw.title,
    description: raw.description,
    url: raw.url,
    displayOrder: raw.display_order,
  };
}
