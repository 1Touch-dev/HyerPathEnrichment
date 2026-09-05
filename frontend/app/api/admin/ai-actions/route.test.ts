import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
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

const rawAction = {
  id: "action-1",
  action_type: "outreach_draft_generated",
  candidate_user_id: "candidate-1",
  triggered_by_user_id: "recruiter-1",
  related_id: "draft-1",
  summary: "Generated an outreach draft",
  created_at: "2026-01-01T00:00:00Z",
};

describe("GET /api/admin/ai-actions", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards filters to the backend and adapts a successful list response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(successEnvelope({ items: [rawAction], next_cursor: null, has_more: false })),
    );

    const response = await GET(
      new NextRequest(
        "http://localhost/api/admin/ai-actions?candidate_id=candidate-1&recruiter_id=recruiter-1&action_type=outreach_draft_generated&since=2026-01-01&until=2026-01-31&cursor=abc&limit=10",
      ),
    );

    expect(backendFetch).toHaveBeenCalledWith(
      "/api/admin/ai-actions?candidate_id=candidate-1&recruiter_id=recruiter-1&action_type=outreach_draft_generated&since=2026-01-01&until=2026-01-31&cursor=abc&limit=10",
    );
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      items: [
        {
          id: "action-1",
          actionType: "outreach_draft_generated",
          candidateUserId: "candidate-1",
          triggeredByUserId: "recruiter-1",
          relatedId: "draft-1",
          summary: "Generated an outreach draft",
          createdAt: "2026-01-01T00:00:00Z",
        },
      ],
      nextCursor: null,
      hasMore: false,
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("FORBIDDEN", "Not allowed", 403), 403),
    );

    const response = await GET(new NextRequest("http://localhost/api/admin/ai-actions"));

    expect(response.status).toBe(403);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("FORBIDDEN");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET(new NextRequest("http://localhost/api/admin/ai-actions"));

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
