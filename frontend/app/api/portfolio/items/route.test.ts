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

function postRequest(body: unknown) {
  return new NextRequest("http://localhost/api/x", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("POST /api/portfolio/items", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method/body (translating itemType) and adapts a successful response", async () => {
    const raw = {
      item_id: "item-1",
      item_type: "github",
      title: "My repo",
      description: "A repo",
      url: "https://github.com/x/y",
      display_order: 0,
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw), 201));

    const response = await POST(
      postRequest({
        itemType: "github_repo",
        title: "My repo",
        description: "A repo",
        url: "https://github.com/x/y",
      }),
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/portfolio/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        item_type: "github",
        title: "My repo",
        description: "A repo",
        url: "https://github.com/x/y",
      }),
    });
    expect(response.status).toBe(201);
    const body = await response.json();
    expect(body.data).toEqual({
      itemId: "item-1",
      itemType: "github_repo",
      title: "My repo",
      description: "A repo",
      url: "https://github.com/x/y",
      displayOrder: 0,
    });
  });

  it("returns a validation error when url is missing", async () => {
    const response = await POST(postRequest({ itemType: "github_repo", title: "x" }));

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("VALIDATION_ERROR", "Bad request", 400), 400),
    );

    const response = await POST(
      postRequest({ itemType: "github_repo", title: "x", url: "https://x.com" }),
    );

    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(
      postRequest({ itemType: "github_repo", title: "x", url: "https://x.com" }),
    );

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
