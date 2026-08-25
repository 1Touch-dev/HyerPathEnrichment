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

const rawRole = {
  id: "role-1",
  name: "recruiter",
  description: "Recruiter role",
  is_system: false,
  permissions: [{ id: "perm-1", resource: "widgets", action: "read", description: null }],
};

describe("GET /api/admin/roles", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards to the backend and adapts a successful list response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope([rawRole])));

    const response = await GET();

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/roles");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual([
      {
        id: "role-1",
        name: "recruiter",
        description: "Recruiter role",
        isSystem: false,
        permissions: [{ id: "perm-1", resource: "widgets", action: "read", description: null }],
      },
    ]);
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET();

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});

describe("POST /api/admin/roles", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the request body and adapts a successful create response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(rawRole), 201));

    const response = await POST(
      new NextRequest("http://localhost/api/admin/roles", {
        method: "POST",
        body: JSON.stringify({ name: "recruiter", description: "Recruiter role" }),
      }),
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "recruiter", description: "Recruiter role" }),
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      id: "role-1",
      name: "recruiter",
      description: "Recruiter role",
      isSystem: false,
      permissions: [{ id: "perm-1", resource: "widgets", action: "read", description: null }],
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("FORBIDDEN", "Not allowed", 403), 403),
    );

    const response = await POST(
      new NextRequest("http://localhost/api/admin/roles", {
        method: "POST",
        body: JSON.stringify({ name: "recruiter" }),
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
      new NextRequest("http://localhost/api/admin/roles", {
        method: "POST",
        body: JSON.stringify({ name: "recruiter" }),
      }),
    );

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
