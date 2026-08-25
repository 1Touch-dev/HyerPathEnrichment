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

const params = { params: Promise.resolve({ sessionId: "sess-1" }) };

describe("POST /api/cv-chat/sessions/[sessionId]/messages", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method/body and adapts the session from the turn wrapper", async () => {
    const raw = {
      session: {
        session_id: "sess-1",
        status: "active",
        missing_fields_at_start: ["summary"],
        fields_resolved: ["summary"],
        messages: [{ id: "m1", role: "user", content: "Hi", created_at: "2024-01-01" }],
      },
      assistant_message: {
        id: "m2",
        role: "assistant",
        content: "Hello",
        created_at: "2024-01-02",
      },
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const response = await POST(postRequest({ content: "Hi" }), params);

    expect(backendFetch).toHaveBeenCalledWith("/api/documents/cv-chat/sessions/sess-1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: "Hi" }),
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      sessionId: "sess-1",
      status: "active",
      missingFieldsAtStart: ["summary"],
      fieldsResolved: ["summary"],
      messages: [{ id: "m1", role: "user", content: "Hi", createdAt: "2024-01-01" }],
    });
  });

  it("returns a validation error when content is missing", async () => {
    const response = await POST(postRequest({}), params);

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns a validation error when content is blank", async () => {
    const response = await POST(postRequest({ content: "   " }), params);

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Session not found", 404), 404),
    );

    const response = await POST(postRequest({ content: "Hi" }), params);

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(postRequest({ content: "Hi" }), params);

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
