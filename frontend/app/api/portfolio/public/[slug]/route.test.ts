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

const params = { params: Promise.resolve({ slug: "jane-doe" }) };

describe("GET /api/portfolio/public/[slug]", () => {
  beforeEach(() => {
    vi.mocked(backendFetchPublic).mockReset();
  });

  it("forwards the correct backend path via backendFetchPublic and adapts a successful response", async () => {
    const raw = {
      slug: "jane-doe",
      display_name: "Jane Doe",
      headline: "Engineer",
      bio: "A bio",
      items: [
        {
          item_id: "item-1",
          item_type: "live_demo",
          title: "Demo",
          description: null,
          url: "https://x.com",
          display_order: 0,
        },
      ],
    };
    vi.mocked(backendFetchPublic).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const response = await GET(new NextRequest("http://localhost/api/x"), params);

    expect(backendFetchPublic).toHaveBeenCalledWith("/api/portfolio/public/jane-doe");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      slug: "jane-doe",
      displayName: "Jane Doe",
      headline: "Engineer",
      summary: "A bio",
      items: [
        {
          itemId: "item-1",
          itemType: "live_demo",
          title: "Demo",
          description: null,
          url: "https://x.com",
          displayOrder: 0,
        },
      ],
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetchPublic).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Profile not found", 404), 404),
    );

    const response = await GET(new NextRequest("http://localhost/api/x"), params);

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetchPublic throws", async () => {
    vi.mocked(backendFetchPublic).mockRejectedValue(new Error("network down"));

    const response = await GET(new NextRequest("http://localhost/api/x"), params);

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
