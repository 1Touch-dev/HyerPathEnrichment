import { describe, it, expect } from "vitest";
import {
  adaptCvFeedbackReport,
  adaptPortfolioProfile,
  adaptPublicBrand,
  adaptPublicPortfolioProfile,
  adaptSwipeDeck,
  mapBackendAdminBrand,
  toBackendBrandCreate,
  toBackendBrandUpdate,
} from "./api-adapter";

// Realistic raw backend-shaped fixtures (matching the real Pydantic schemas) run
// through the real adapters — regression coverage for fields that previously
// drifted between the backend schemas and the hand-maintained `Raw*Response`
// interfaces in this file.

describe("adaptSwipeDeck", () => {
  it("maps has_more from the real SwipeDeckResponse shape (backend/app/modules/job_swipe/schemas.py)", () => {
    const raw = {
      cards: [
        {
          match_id: "m1",
          job_posting_id: "jp1",
          title: "Senior Engineer",
          company: "Acme",
          location: "Remote",
          remote: true,
          salary_min: null,
          salary_max: null,
          salary_currency: null,
          overall_score: 88,
          explanation: null,
          below_similarity_threshold: false,
          source_url: "https://example.com/job/1",
          applied_at: null,
        },
      ],
      has_more: true,
    };

    const deck = adaptSwipeDeck(raw);

    expect(deck.hasMore).toBe(true);
    expect(deck.cards).toHaveLength(1);
    expect(deck.cards[0]).not.toHaveProperty("scoreBreakdown");
    expect(deck.cards[0].belowSimilarityThreshold).toBe(false);
    expect(deck.cards[0].sourceUrl).toBe("https://example.com/job/1");
    expect(deck.cards[0].appliedAt).toBeNull();
  });

  it("maps has_more: false", () => {
    const raw = { cards: [], has_more: false };
    expect(adaptSwipeDeck(raw).hasMore).toBe(false);
  });
});

describe("adaptPortfolioProfile", () => {
  it("maps display_name/user_id/public_url from the real PortfolioProfileResponse shape (backend/app/modules/portfolio/schemas.py)", () => {
    const raw = {
      profile_id: "p1",
      user_id: "u1",
      slug: "jane-doe",
      display_name: "Jane Doe",
      headline: "Backend Engineer",
      bio: "I build things.",
      is_published: true,
      public_url: "/p/jane-doe",
      items: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };

    const profile = adaptPortfolioProfile(raw);

    expect(profile.displayName).toBe("Jane Doe");
    expect(profile.userId).toBe("u1");
    expect(profile.publicUrl).toBe("/p/jane-doe");
  });
});

describe("adaptPublicPortfolioProfile", () => {
  it("maps display_name from the real PublicPortfolioResponse shape (backend/app/modules/portfolio/schemas.py)", () => {
    const raw = {
      slug: "jane-doe",
      display_name: "Jane Doe",
      headline: "Backend Engineer",
      bio: "I build things.",
      items: [],
    };

    const profile = adaptPublicPortfolioProfile(raw);

    expect(profile.displayName).toBe("Jane Doe");
    expect(profile).not.toHaveProperty("userId");
    expect(profile).not.toHaveProperty("publicUrl");
  });
});

describe("adaptPublicBrand", () => {
  it("maps name/slug/landing_page_tier_config and drops admin-only fields", () => {
    const raw = {
      name: "Acme Staffing",
      slug: "acme-staffing",
      landing_page_tier_config: { headline: "Join Acme", tiers: ["free"] },
      id: "should-drop",
      custom_domain: "acme.example",
      chatbot_config: { widget: true },
      is_active: true,
    };

    const brand = adaptPublicBrand(raw);

    expect(brand).toEqual({
      name: "Acme Staffing",
      slug: "acme-staffing",
      landingPageTierConfig: { headline: "Join Acme", tiers: ["free"] },
    });
    expect(brand).not.toHaveProperty("id");
    expect(brand).not.toHaveProperty("customDomain");
    expect(brand).not.toHaveProperty("chatbotConfig");
    expect(brand).not.toHaveProperty("isActive");
  });
});

describe("mapBackendAdminBrand", () => {
  it("maps BrandResponse snake_case including is_active", () => {
    const mapped = mapBackendAdminBrand({
      id: "b1",
      name: "Acme",
      slug: "acme",
      custom_domain: null,
      chatbot_config: null,
      landing_page_tier_config: { headline: "Join" },
      is_active: false,
      created_at: "2026-01-01T00:00:00Z",
    });

    expect(mapped.isActive).toBe(false);
    expect(mapped.customDomain).toBeNull();
    expect(mapped.landingPageTierConfig).toEqual({ headline: "Join" });
  });
});

describe("toBackendBrandCreate", () => {
  it("always sends name + slug and omits undefined optionals", () => {
    expect(toBackendBrandCreate({ name: "Acme", slug: "acme" })).toEqual({
      name: "Acme",
      slug: "acme",
    });
  });
});

describe("toBackendBrandUpdate", () => {
  it("serializes a name-only payload with no other keys", () => {
    expect(toBackendBrandUpdate({ name: "Acme" })).toEqual({ name: "Acme" });
  });

  it("emits custom_domain: null for an explicit clear", () => {
    expect(toBackendBrandUpdate({ customDomain: null })).toEqual({
      custom_domain: null,
    });
  });

  it("omits custom_domain when customDomain is undefined", () => {
    expect(toBackendBrandUpdate({ customDomain: undefined })).not.toHaveProperty("custom_domain");
  });

  it("never emits is_active / isActive even if extras are cast in", () => {
    const sneaky = {
      name: "Acme",
      isActive: false,
      is_active: false,
    } as Parameters<typeof toBackendBrandUpdate>[0] & {
      isActive: boolean;
      is_active: boolean;
    };

    const payload = toBackendBrandUpdate(sneaky);
    expect(payload).toEqual({ name: "Acme" });
    expect(payload).not.toHaveProperty("is_active");
    expect(payload).not.toHaveProperty("isActive");
  });
});

describe("adaptCvFeedbackReport", () => {
  it("maps target_role and accepted_bullet_indices from the real CvFeedbackResponse shape (backend/app/modules/documents/schemas.py)", () => {
    const raw = {
      report_id: "r1",
      document_id: "doc1",
      target_role: "Staff Engineer",
      ats_score: 75,
      strengths: [],
      improvements: [],
      rewritten_bullets: [
        {
          original: "Worked on backend",
          rewritten: "Built backend serving 1M+ users",
          rationale: "Quantifies impact",
        },
      ],
      accepted_bullet_indices: [0],
      created_at: "2026-01-01T00:00:00Z",
    };

    const report = adaptCvFeedbackReport(raw);

    expect(report.targetRole).toBe("Staff Engineer");
    expect(report.acceptedBulletIndices).toEqual([0]);
  });

  it("maps a null target_role and an empty accepted_bullet_indices list", () => {
    const raw = {
      report_id: "r1",
      document_id: "doc1",
      target_role: null,
      ats_score: 75,
      strengths: [],
      improvements: [],
      rewritten_bullets: [],
      accepted_bullet_indices: [],
      created_at: "2026-01-01T00:00:00Z",
    };

    const report = adaptCvFeedbackReport(raw);

    expect(report.targetRole).toBeNull();
    expect(report.acceptedBulletIndices).toEqual([]);
  });
});
