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

const params = { params: Promise.resolve({ documentId: "doc-1" }) };

describe("POST /api/documents/[documentId]/cv-chat/sessions", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method and adapts a successful response", async () => {
    const raw = {
      session_id: "sess-1",
      status: "active",
      missing_fields_at_start: ["summary"],
      fields_resolved: [],
      messages: [{ id: "m1", role: "assistant", content: "Hi", created_at: "2024-01-01" }],
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const response = await POST(new NextRequest("http://localhost/api/x"), params);

    expect(backendFetch).toHaveBeenCalledWith("/api/documents/doc-1/cv-chat/sessions", {
      method: "POST",
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      sessionId: "sess-1",
      status: "active",
      missingFieldsAtStart: ["summary"],
      fieldsResolved: [],
      messages: [{ id: "m1", role: "assistant", content: "Hi", createdAt: "2024-01-01" }],
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Document not found", 404), 404),
    );

    const response = await POST(new NextRequest("http://localhost/api/x"), params);

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(new NextRequest("http://localhost/api/x"), params);

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
