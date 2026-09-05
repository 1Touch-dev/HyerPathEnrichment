import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { successEnvelope, errorEnvelope } from "@/src/lib/api-envelope";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("POST /api/outreach/linkedin-send-batches", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("rejects a request missing maxSendsPerDay before reaching the backend", async () => {
    const request = new NextRequest("http://localhost/api/outreach/linkedin-send-batches", {
      method: "POST",
      body: JSON.stringify({ multiloginProfileId: "profile-1" }),
    });

    const response = await POST(request);

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.success).toBe(false);
  });

  it("forwards a valid request and adapts a successful response", async () => {
    const raw = {
      id: "b1",
      triggered_by: "u1",
      multilogin_profile_id: "profile-1",
      status: "pending",
      max_sends_per_day: 5,
      started_at: null,
      completed_at: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const request = new NextRequest("http://localhost/api/outreach/linkedin-send-batches", {
      method: "POST",
      body: JSON.stringify({ multiloginProfileId: "profile-1", maxSendsPerDay: 5, taskIds: [] }),
    });
    const response = await POST(request);

    expect(backendFetch).toHaveBeenCalledWith("/api/outreach/linkedin-send-batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        multilogin_profile_id: "profile-1",
        max_sends_per_day: 5,
        task_ids: [],
      }),
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      id: "b1",
      triggeredBy: "u1",
      multiloginProfileId: "profile-1",
      status: "pending",
      maxSendsPerDay: 5,
      startedAt: null,
      completedAt: null,
      createdAt: "2026-01-01T00:00:00Z",
    });
  });

  it("translates a failing backend response (e.g. 422) through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(
        errorEnvelope("VALIDATION_ERROR", "max_sends_per_day must be positive", 422),
        422,
      ),
    );

    const request = new NextRequest("http://localhost/api/outreach/linkedin-send-batches", {
      method: "POST",
      body: JSON.stringify({ multiloginProfileId: "profile-1", maxSendsPerDay: 5 }),
    });
    const response = await POST(request);

    expect(response.status).toBe(422);
    const body = await response.json();
    expect(body.success).toBe(false);
  });
});
