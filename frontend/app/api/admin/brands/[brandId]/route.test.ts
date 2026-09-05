import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { GET, PATCH } from "./route";
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
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

const mappedBrand = {
  id: "b1",
  name: "Acme",
  slug: "acme",
  customDomain: null,
  chatbotConfig: null,
  landingPageTierConfig: { headline: "Join" },
  isActive: true,
  createdAt: "2026-01-01T00:00:00Z",
};

describe("GET /api/admin/brands/[brandId]", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards to the backend and adapts a successful detail response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawBrand)));

    const response = await GET(new NextRequest("http://localhost/api/admin/brands/b1"), {
      params: Promise.resolve({ brandId: "b1" }),
    });

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/brands/b1");
    expect(vi.mocked(backendFetch).mock.calls[0][0]).not.toContain("/api/orgs");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(mappedBrand);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Not found", 404), 404),
    );

    const response = await GET(new NextRequest("http://localhost/api/admin/brands/missing"), {
      params: Promise.resolve({ brandId: "missing" }),
    });

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET(new NextRequest("http://localhost/api/admin/brands/b1"), {
      params: Promise.resolve({ brandId: "b1" }),
    });

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});

describe("PATCH /api/admin/brands/[brandId]", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("maps camelCase through toBackendBrandUpdate and never emits is_active", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawBrand)));

    const response = await PATCH(
      new NextRequest("http://localhost/api/admin/brands/b1", {
        method: "PATCH",
        headers: { "Idempotency-Key": "brand-update-1" },
        body: JSON.stringify({
          name: "Acme",
          isActive: false,
          is_active: false,
        }),
      }),
      { params: Promise.resolve({ brandId: "b1" }) },
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/brands/b1", {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "Idempotency-Key": "brand-update-1" },
      body: JSON.stringify({ name: "Acme" }),
    });
    const forwarded = JSON.parse(
      (vi.mocked(backendFetch).mock.calls[0][1] as { body: string }).body,
    ) as Record<string, unknown>;
    expect(forwarded).not.toHaveProperty("is_active");
    expect(forwarded).not.toHaveProperty("isActive");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(mappedBrand);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("FORBIDDEN", "Not allowed", 403), 403),
    );

    const response = await PATCH(
      new NextRequest("http://localhost/api/admin/brands/b1", {
        method: "PATCH",
        headers: { "Idempotency-Key": "brand-update-2" },
        body: JSON.stringify({ name: "Acme" }),
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

    const response = await PATCH(
      new NextRequest("http://localhost/api/admin/brands/b1", {
        method: "PATCH",
        body: JSON.stringify({ name: "Acme" }),
      }),
      { params: Promise.resolve({ brandId: "b1" }) },
    );

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
