import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "./route";
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

describe("GET /api/admin/brands", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards to /api/admin/brands and maps the list via mapBackendAdminBrand", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope([rawBrand])));

    const response = await GET();

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/brands");
    expect(vi.mocked(backendFetch).mock.calls[0][0]).not.toContain("/api/orgs");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual([mappedBrand]);
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET();

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});

describe("POST /api/admin/brands", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards camelCase create to /api/admin/brands and returns 200 even if backend is 201", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawBrand), 201));

    const response = await POST(
      new NextRequest("http://localhost/api/admin/brands", {
        method: "POST",
        body: JSON.stringify({
          name: "Acme",
          slug: "acme",
          customDomain: "acme.example",
        }),
      }),
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/brands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Acme",
        slug: "acme",
        custom_domain: "acme.example",
      }),
    });
    expect(vi.mocked(backendFetch).mock.calls[0][0]).not.toContain("/api/orgs");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(mappedBrand);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("FORBIDDEN", "Not allowed", 403), 403),
    );

    const response = await POST(
      new NextRequest("http://localhost/api/admin/brands", {
        method: "POST",
        body: JSON.stringify({ name: "Acme", slug: "acme" }),
      }),
    );

    expect(response.status).toBe(403);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("FORBIDDEN");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(
      new NextRequest("http://localhost/api/admin/brands", {
        method: "POST",
        body: JSON.stringify({ name: "Acme", slug: "acme" }),
      }),
    );

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
