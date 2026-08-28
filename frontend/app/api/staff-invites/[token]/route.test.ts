import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "./route";
import { backendFetchPublic } from "@/src/lib/backend-client";
import { successEnvelope, errorEnvelope } from "@/src/lib/api-envelope";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

const params = { params: Promise.resolve({ token: "abc123" }) };

describe("GET /api/staff-invites/[token]", () => {
  beforeEach(() => {
    vi.mocked(backendFetchPublic).mockReset();
  });

  it("forwards the correct backend path via backendFetchPublic", async () => {
    vi.mocked(backendFetchPublic).mockResolvedValue(
      jsonResponse(
        successEnvelope({
          invited_by_name: "Jane Doe",
          role_name: "recruiter",
          email: "invitee@example.com",
          expires_at: "2026-02-01T00:00:00Z",
        }),
      ),
    );

    await GET(new NextRequest("http://localhost/api/staff-invites/abc123"), params);

    expect(backendFetchPublic).toHaveBeenCalledWith("/api/staff-invites/abc123");
  });

  it("passes through a 200 response with the expected fields intact", async () => {
    vi.mocked(backendFetchPublic).mockResolvedValue(
      jsonResponse(
        successEnvelope({
          invited_by_name: "Jane Doe",
          role_name: "recruiter",
          email: "invitee@example.com",
          expires_at: "2026-02-01T00:00:00Z",
        }),
      ),
    );

    const response = await GET(
      new NextRequest("http://localhost/api/staff-invites/abc123"),
      params,
    );

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      invited_by_name: "Jane Doe",
      role_name: "recruiter",
      email: "invitee@example.com",
      expires_at: "2026-02-01T00:00:00Z",
    });
  });

  it("passes through a 404 from the backend as a 404 (unknown token), not a 200 or 500", async () => {
    vi.mocked(backendFetchPublic).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Invite not found", 404), 404),
    );

    const response = await GET(
      new NextRequest("http://localhost/api/staff-invites/unknown"),
      params,
    );

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("passes through a 410 from the backend as a 410 (accepted or expired invite)", async () => {
    vi.mocked(backendFetchPublic).mockResolvedValue(
      jsonResponse(errorEnvelope("GONE", "Invite already accepted", 410), 410),
    );

    const response = await GET(
      new NextRequest("http://localhost/api/staff-invites/expired"),
      params,
    );

    expect(response.status).toBe(410);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.message).toBe("Invite already accepted");
  });

  it("returns bffServiceUnavailable (502) when backendFetchPublic throws", async () => {
    vi.mocked(backendFetchPublic).mockRejectedValue(new Error("network down"));

    const response = await GET(
      new NextRequest("http://localhost/api/staff-invites/abc123"),
      params,
    );

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
