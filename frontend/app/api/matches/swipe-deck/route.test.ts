import { describe, it, expect, vi, beforeEach } from "vitest";
import { GET } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { successEnvelope, errorEnvelope } from "@/src/lib/api-envelope";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("GET /api/matches/swipe-deck", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path and adapts a successful response", async () => {
    const raw = {
      cards: [
        {
          match_id: "m1",
          job_posting_id: "jp1",
          title: "Engineer",
          company: "Acme",
          location: "Remote",
          remote: true,
          salary_min: null,
          salary_max: null,
          salary_currency: null,
          overall_score: 90,
          explanation: "Great fit",
        },
      ],
      has_more: false,
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const response = await GET();

    expect(backendFetch).toHaveBeenCalledWith("/api/matches/swipe-deck");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      cards: [
        {
          matchId: "m1",
          jobPostingId: "jp1",
          title: "Engineer",
          company: "Acme",
          location: "Remote",
          remote: true,
          salaryMin: null,
          salaryMax: null,
          salaryCurrency: null,
          overallScore: 90,
          explanation: "Great fit",
        },
      ],
      hasMore: false,
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("UNAUTHORIZED", "Not logged in", 401), 401),
    );

    const response = await GET();

    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET();

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
