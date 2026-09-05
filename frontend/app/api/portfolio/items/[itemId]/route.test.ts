import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { DELETE } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { errorEnvelope } from "@/src/lib/api-envelope";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

const params = { params: Promise.resolve({ itemId: "item-1" }) };

describe("DELETE /api/portfolio/items/[itemId]", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method and returns deleted:true on success", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse({}, 200));

    const response = await DELETE(new NextRequest("http://localhost/api/x"), params);

    expect(backendFetch).toHaveBeenCalledWith("/api/portfolio/items/item-1", {
      method: "DELETE",
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({ deleted: true });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Item not found", 404), 404),
    );

    const response = await DELETE(new NextRequest("http://localhost/api/x"), params);

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await DELETE(new NextRequest("http://localhost/api/x"), params);

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
