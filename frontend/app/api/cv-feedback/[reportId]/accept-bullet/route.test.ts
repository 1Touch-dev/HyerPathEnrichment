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

const params = { params: Promise.resolve({ reportId: "rep-1" }) };

describe("POST /api/cv-feedback/[reportId]/accept-bullet", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method/body and returns accepted:true on success", async () => {
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope({ accepted: true })));

    const response = await POST(postRequest({ bulletIndex: 2, documentId: "doc-1" }), params);

    expect(backendFetch).toHaveBeenCalledWith("/api/documents/doc-1/feedback/rep-1/accept", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bullet_index: 2 }),
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({ accepted: true });
  });

  it("returns a validation error when bulletIndex is not a number", async () => {
    const response = await POST(postRequest({ documentId: "doc-1" }), params);

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns a validation error when documentId is missing", async () => {
    const response = await POST(postRequest({ bulletIndex: 0 }), params);

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Report not found", 404), 404),
    );

    const response = await POST(postRequest({ bulletIndex: 0, documentId: "doc-1" }), params);

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(postRequest({ bulletIndex: 0, documentId: "doc-1" }), params);

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
