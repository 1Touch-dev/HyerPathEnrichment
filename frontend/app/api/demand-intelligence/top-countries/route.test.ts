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

describe("GET /api/demand-intelligence/top-countries", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the role and limit query params and returns a successful response", async () => {
    const raw = {
      role: "software engineer",
      results: [
        {
          country_iso2: "us",
          role_bucket: "software engineer",
          posting_count: 120,
          remote_posting_count: 40,
          avg_salary_min: 90000,
          avg_salary_max: 140000,
          snapshot_date: "2026-08-01",
          tier: "tier_1",
        },
      ],
      generated_at: "2026-08-01T00:00:00Z",
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const response = await GET(
      new NextRequest(
        "http://localhost/api/demand-intelligence/top-countries?role=software+engineer&limit=5",
      ),
    );

    expect(backendFetch).toHaveBeenCalledWith(
      "/api/demand-intelligence/top-countries?role=software+engineer&limit=5",
    );
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(raw);
  });

  it("omits limit from the forwarded query string when it was not provided", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(
        successEnvelope({ role: "nurse", results: [], generated_at: "2026-08-01T00:00:00Z" }),
      ),
    );

    await GET(new NextRequest("http://localhost/api/demand-intelligence/top-countries?role=nurse"));

    expect(backendFetch).toHaveBeenCalledWith("/api/demand-intelligence/top-countries?role=nurse");
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("UNAUTHORIZED", "Not logged in", 401), 401),
    );

    const response = await GET(
      new NextRequest("http://localhost/api/demand-intelligence/top-countries?role=nurse"),
    );

    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET(
      new NextRequest("http://localhost/api/demand-intelligence/top-countries?role=nurse"),
    );

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
