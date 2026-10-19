import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { errorEnvelope, successEnvelope } from "@/src/lib/api-envelope";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

const rawInvite = {
  id: "invite-1",
  email: "teammate@example.com",
  role_name: "recruiter",
  expires_at: "2026-10-20T00:00:00Z",
  accepted_at: null,
  invite_token: "plain-token",
};

const createBody = {
  email: "teammate@example.com",
  confirmation_email: "teammate@example.com",
  mfa_code: "123456",
  role_name: "recruiter" as const,
};

describe("POST /api/admin/staff-invites", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the hardened payload, idempotency key, and 201 invite", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawInvite), 201));

    const response = await POST(
      new NextRequest("http://localhost/api/admin/staff-invites", {
        method: "POST",
        headers: { "Idempotency-Key": "staff-invite-1", "Content-Type": "application/json" },
        body: JSON.stringify(createBody),
      }),
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/staff-invites", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": "staff-invite-1",
      },
      body: JSON.stringify(createBody),
    });
    expect(response.status).toBe(201);
    await expect(response.json()).resolves.toMatchObject({
      success: true,
      data: rawInvite,
    });
  });

  it("synthesizes an Idempotency-Key when the browser omits one", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawInvite), 201));

    const response = await POST(
      new NextRequest("http://localhost/api/admin/staff-invites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "teammate@example.com",
          confirmation_email: "teammate@example.com",
          mfa_code: "654321",
        }),
      }),
    );

    expect(response.status).toBe(201);
    const forwarded = vi.mocked(backendFetch).mock.calls[0]?.[1] as {
      headers: Record<string, string>;
      body: string;
    };
    expect(forwarded.headers["Idempotency-Key"]).toMatch(/^staff-invite:/);
    expect(JSON.parse(forwarded.body)).toEqual({
      email: "teammate@example.com",
      confirmation_email: "teammate@example.com",
      mfa_code: "654321",
      role_name: "recruiter",
    });
  });

  it("translates a 422 backend failure through the envelope", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("VALIDATION_ERROR", "Unprocessable Content", 422), 422),
    );

    const response = await POST(
      new NextRequest("http://localhost/api/admin/staff-invites", {
        method: "POST",
        headers: { "Idempotency-Key": "staff-invite-422", "Content-Type": "application/json" },
        body: JSON.stringify(createBody),
      }),
    );

    expect(response.status).toBe(422);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      error: { code: "VALIDATION_ERROR" },
    });
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(
      new NextRequest("http://localhost/api/admin/staff-invites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(createBody),
      }),
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      error: { code: "SERVICE_UNAVAILABLE" },
    });
  });
});
