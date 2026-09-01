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

const rawBrand = {
  id: "b1",
  name: "Acme",
  slug: "acme",
  custom_domain: null,
  chatbot_config: null,
  landing_page_tier_config: { headline: "Join" },
  is_active: false,
  created_at: "2026-01-01T00:00:00Z",
};

const mappedBrand = {
  id: "b1",
  name: "Acme",
  slug: "acme",
  customDomain: null,
  chatbotConfig: null,
  landingPageTierConfig: { headline: "Join" },
  isActive: false,
  createdAt: "2026-01-01T00:00:00Z",
};

function forwardedBody(): Record<string, unknown> {
  return JSON.parse((vi.mocked(backendFetch).mock.calls[0][1] as { body: string }).body) as Record<
    string,
    unknown
  >;
}

describe("POST /api/admin/brands/[brandId]/deactivate", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards to the backend deactivate path with JSON {} when no reason is provided", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawBrand)));

    const response = await POST(
      new NextRequest("http://localhost/api/admin/brands/b1/deactivate", {
        method: "POST",
        body: JSON.stringify({}),
      }),
      { params: Promise.resolve({ brandId: "b1" }) },
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/brands/b1/deactivate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(vi.mocked(backendFetch).mock.calls[0][0]).not.toContain("/api/orgs");
    expect(forwardedBody()).toEqual({});
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(mappedBrand);
  });

  it("forwards JSON {} when the request has no body or an empty reason", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawBrand)));

    const noBody = await POST(
      new NextRequest("http://localhost/api/admin/brands/b1/deactivate", { method: "POST" }),
      { params: Promise.resolve({ brandId: "b1" }) },
    );

    expect(noBody.status).toBe(200);
    expect(backendFetch).toHaveBeenCalledWith("/api/admin/brands/b1/deactivate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(forwardedBody()).toEqual({});

    vi.mocked(backendFetch).mockReset();
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawBrand)));

    const emptyReason = await POST(
      new NextRequest("http://localhost/api/admin/brands/b1/deactivate", {
        method: "POST",
        body: JSON.stringify({ reason: "   " }),
      }),
      { params: Promise.resolve({ brandId: "b1" }) },
    );

    expect(emptyReason.status).toBe(200);
    expect(backendFetch).toHaveBeenCalledWith("/api/admin/brands/b1/deactivate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(forwardedBody()).toEqual({});
  });

  it("forwards JSON { reason } when a reason is provided and adapts the brand payload", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawBrand)));

    const response = await POST(
      new NextRequest("http://localhost/api/admin/brands/b1/deactivate", {
        method: "POST",
        body: JSON.stringify({ reason: "  sunset  " }),
      }),
      { params: Promise.resolve({ brandId: "b1" }) },
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/brands/b1/deactivate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "sunset" }),
    });
    expect(vi.mocked(backendFetch).mock.calls[0][0]).not.toContain("/api/orgs");
    expect(forwardedBody()).toEqual({ reason: "sunset" });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(mappedBrand);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("FORBIDDEN", "Not allowed", 403), 403),
    );

    const response = await POST(
      new NextRequest("http://localhost/api/admin/brands/b1/deactivate", {
        method: "POST",
        body: JSON.stringify({}),
      }),
      { params: Promise.resolve({ brandId: "b1" }) },
    );

    expect(response.status).toBe(403);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("FORBIDDEN");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(
      new NextRequest("http://localhost/api/admin/brands/b1/deactivate", {
        method: "POST",
        body: JSON.stringify({}),
      }),
      { params: Promise.resolve({ brandId: "b1" }) },
    );

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
