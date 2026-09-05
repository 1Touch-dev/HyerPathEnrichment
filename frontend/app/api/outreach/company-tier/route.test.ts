import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { GET, PUT } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { successEnvelope, errorEnvelope } from "@/src/lib/api-envelope";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function getRequest(query: string) {
  return new NextRequest(`http://localhost/api/outreach/company-tier${query}`);
}

function putRequest(body: unknown) {
  return new NextRequest("http://localhost/api/outreach/company-tier", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const rawTier = {
  company_name: "Acme",
  tier: "premium",
  notes: "Great culture",
  updated_at: "2024-01-02T00:00:00Z",
};

const adaptedTier = {
  companyName: "Acme",
  tier: "premium",
  notes: "Great culture",
  updatedAt: "2024-01-02T00:00:00Z",
};

describe("GET /api/outreach/company-tier", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path and adapts a successful response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawTier)));

    const response = await GET(getRequest("?companyName=Acme"));

    expect(backendFetch).toHaveBeenCalledWith("/api/outreach/company-tier?company_name=Acme");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(adaptedTier);
  });

  it("URL-encodes companyName when forwarding to the backend", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawTier)));

    await GET(getRequest("?companyName=Acme%20%26%20Co"));

    expect(backendFetch).toHaveBeenCalledWith(
      "/api/outreach/company-tier?company_name=Acme%20%26%20Co",
    );
  });

  it("returns a null data payload when the backend has no tier set yet", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(null)));

    const response = await GET(getRequest("?companyName=Unknown"));

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toBeNull();
  });

  it("returns a validation error when companyName is missing", async () => {
    const response = await GET(getRequest(""));

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("UNAUTHORIZED", "Not allowed", 401), 401),
    );

    const response = await GET(getRequest("?companyName=Acme"));

    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET(getRequest("?companyName=Acme"));

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});

describe("PUT /api/outreach/company-tier", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method/body and adapts a successful response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawTier)));

    const response = await PUT(
      putRequest({ companyName: "Acme", tier: "premium", notes: "Great culture" }),
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/outreach/company-tier", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_name: "Acme",
        tier: "premium",
        notes: "Great culture",
      }),
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(adaptedTier);
  });

  it("defaults notes to null when omitted", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawTier)));

    await PUT(putRequest({ companyName: "Acme", tier: "outsourcing" }));

    expect(backendFetch).toHaveBeenCalledWith("/api/outreach/company-tier", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_name: "Acme",
        tier: "outsourcing",
        notes: null,
      }),
    });
  });

  it("returns a validation error when companyName is missing", async () => {
    const response = await PUT(putRequest({ tier: "premium" }));

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
  });

  it("returns a validation error when tier is missing", async () => {
    const response = await PUT(putRequest({ companyName: "Acme" }));

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("VALIDATION_ERROR", "Bad tier", 400), 400),
    );

    const response = await PUT(putRequest({ companyName: "Acme", tier: "premium" }));

    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await PUT(putRequest({ companyName: "Acme", tier: "premium" }));

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
