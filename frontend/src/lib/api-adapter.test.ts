import { describe, it, expect } from "vitest";
import {
  adaptCvFeedbackReport,
  adaptPortfolioProfile,
  adaptPublicPortfolioProfile,
  adaptSwipeDeck,
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
        },
      ],
      has_more: true,
    };

    const deck = adaptSwipeDeck(raw);

    expect(deck.hasMore).toBe(true);
    expect(deck.cards).toHaveLength(1);
    expect(deck.cards[0]).not.toHaveProperty("scoreBreakdown");
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
