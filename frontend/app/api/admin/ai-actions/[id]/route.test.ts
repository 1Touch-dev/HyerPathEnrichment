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

describe("GET /api/admin/ai-actions/[id]", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards to the backend and adapts a successful detail response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawAction)));

    const response = await GET(new NextRequest("http://localhost/api/admin/ai-actions/action-1"), {
      params: Promise.resolve({ id: "action-1" }),
    });

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/ai-actions/action-1");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      id: "action-1",
      actionType: "outreach_draft_generated",
      candidateUserId: "candidate-1",
      triggeredByUserId: "recruiter-1",
      relatedId: "draft-1",
      summary: "Generated an outreach draft",
      createdAt: "2026-01-01T00:00:00Z",
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Not found", 404), 404),
    );

    const response = await GET(new NextRequest("http://localhost/api/admin/ai-actions/missing"), {
      params: Promise.resolve({ id: "missing" }),
    });

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET(new NextRequest("http://localhost/api/admin/ai-actions/action-1"), {
      params: Promise.resolve({ id: "action-1" }),
    });

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
