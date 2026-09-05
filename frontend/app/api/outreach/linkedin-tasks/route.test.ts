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

describe("GET /api/outreach/linkedin-tasks", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the status query param and adapts a successful response", async () => {
    const raw = {
      tasks: [
        {
          id: "t1",
          outreach_message_id: "m1",
          batch_id: null,
          linkedin_profile_url: "https://www.linkedin.com/in/jane",
          action_type: "direct_message",
          status: "pending",
          claimed_by: null,
          claimed_at: null,
          completed_at: null,
          outcome_note: null,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const response = await GET(
      new NextRequest("http://localhost/api/outreach/linkedin-tasks?status=pending"),
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/outreach/linkedin-tasks?status=pending");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual([
      {
        id: "t1",
        outreachMessageId: "m1",
        batchId: null,
        linkedinProfileUrl: "https://www.linkedin.com/in/jane",
        actionType: "direct_message",
        status: "pending",
        claimedBy: null,
        claimedAt: null,
        completedAt: null,
        outcomeNote: null,
        createdAt: "2026-01-01T00:00:00Z",
      },
    ]);
  });

  it("translates a failing backend response (e.g. 403) through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(
        errorEnvelope("FORBIDDEN", "Missing permission: linkedin_tasks:operate", 403),
        403,
      ),
    );

    const response = await GET(new NextRequest("http://localhost/api/outreach/linkedin-tasks"));

    expect(response.status).toBe(403);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("FORBIDDEN");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET(new NextRequest("http://localhost/api/outreach/linkedin-tasks"));

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
