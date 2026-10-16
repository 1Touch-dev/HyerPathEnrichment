import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { GET, PUT } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { successEnvelope, errorEnvelope } from "@/src/lib/api-envelope";
import { adaptPortfolioProfile } from "@/src/lib/api-adapter";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function putRequest(body: unknown) {
  return new NextRequest("http://localhost/api/x", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const rawProfile = {
  profile_id: "prof-1",
  user_id: "user-1",
  slug: "jane-doe",
  display_name: "Jane Doe",
  headline: "Engineer",
  bio: "A bio",
  is_published: true,
  public_url: "https://example.com/p/jane-doe",
  items: [],
  created_at: "2024-01-01",
  updated_at: "2024-01-02",
};

const adaptedProfile = adaptPortfolioProfile(rawProfile);

describe("GET /api/portfolio/profile", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path and adapts a successful response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawProfile)));

    const response = await GET();

    expect(backendFetch).toHaveBeenCalledWith("/api/portfolio/profile");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(adaptedProfile);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Profile not found", 404), 404),
    );

    const response = await GET();

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET();

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});

describe("PUT /api/portfolio/profile", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method/body and adapts a successful response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawProfile)));

    const response = await PUT(
      putRequest({ slug: "jane-doe", headline: "Engineer", summary: "A bio", isPublished: true }),
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/portfolio/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slug: "jane-doe",
        display_name: null,
        headline: "Engineer",
        bio: "A bio",
        is_published: true,
        publish: false,
      }),
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual(adaptedProfile);
  });

  it("forwards studio fields when provided", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawProfile)));

    await PUT(
      putRequest({
        slug: "jane-doe",
        templateId: "developer_dark",
        theme: { palette: "ocean", accent: null, fontPairing: "mono" },
        content: {
          displayName: "Jane",
          professionalRole: null,
          location: null,
          headline: "Hi",
          summary: null,
          about: null,
          profileImageUrl: null,
          coverImageUrl: null,
          email: null,
          resumeUrl: null,
          projects: [],
          experience: [],
          education: [],
          skills: [],
          certifications: [],
          socialLinks: [],
        },
        isPublished: false,
      }),
    );

    const call = vi.mocked(backendFetch).mock.calls[0];
    const forwarded = JSON.parse(String(call[1]?.body));
    expect(forwarded.template_id).toBe("developer_dark");
    expect(forwarded.theme.font_pairing).toBe("mono");
    expect(forwarded.content.display_name).toBe("Jane");
  });

  it("returns a validation error when slug is missing", async () => {
    const response = await PUT(putRequest({ headline: "Engineer" }));

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("CONFLICT", "Slug already taken", 409), 409),
    );

    const response = await PUT(putRequest({ slug: "taken" }));

    expect(response.status).toBe(409);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("CONFLICT");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await PUT(putRequest({ slug: "jane-doe" }));

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
