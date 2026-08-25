import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { errorEnvelope } from "@/src/lib/api-envelope";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function emptyResponse(status = 204): Response {
  return new Response(null, { status });
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

const params = { params: Promise.resolve({ roleId: "role-1" }) };

describe("POST /api/admin/roles/[roleId]/permissions", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method/body and passes through the 204 status", async () => {
    vi.mocked(backendFetch).mockResolvedValue(emptyResponse(204));

    const response = await POST(
      new NextRequest("http://localhost/api/x", {
        method: "POST",
        body: JSON.stringify({ permission_id: "perm-1" }),
      }),
      params,
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/roles/role-1/permissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ permission_id: "perm-1" }),
    });
    expect(response.status).toBe(204);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Role not found", 404), 404),
    );

    const response = await POST(
      new NextRequest("http://localhost/api/x", {
        method: "POST",
        body: JSON.stringify({ permission_id: "perm-1" }),
      }),
      params,
    );

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(
      new NextRequest("http://localhost/api/x", {
        method: "POST",
        body: JSON.stringify({ permission_id: "perm-1" }),
      }),
      params,
    );

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
