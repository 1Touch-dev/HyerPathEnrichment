import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { PATCH } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { successEnvelope, errorEnvelope } from "@/src/lib/api-envelope";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function patchRequest(body: unknown) {
  return new NextRequest("http://localhost/api/x", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const params = { params: Promise.resolve({ messageId: "msg-1" }) };

describe("PATCH /api/outreach/[messageId]", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method/body and adapts a successful response", async () => {
    const raw = {
      message_id: "msg-1",
      company_name: "Acme",
      recipient_role_title: null,
      subject: "New subject",
      body: "New body",
      status: "draft",
      sent_at: null,
      created_at: "2024-01-01",
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const response = await PATCH(
      patchRequest({ subject: "New subject", body: "New body" }),
      params,
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/outreach/msg-1", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: "New subject", body: "New body" }),
    });
    expect(response.status).toBe(200);
    const responseBody = await response.json();
    expect(responseBody.data).toEqual({
      messageId: "msg-1",
      companyName: "Acme",
      recipientRoleTitle: null,
      subject: "New subject",
      body: "New body",
      status: "draft",
      createdAt: "2024-01-01",
      sentAt: null,
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Message not found", 404), 404),
    );

    const response = await PATCH(patchRequest({ subject: "s", body: "b" }), params);

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await PATCH(patchRequest({ subject: "s", body: "b" }), params);

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
