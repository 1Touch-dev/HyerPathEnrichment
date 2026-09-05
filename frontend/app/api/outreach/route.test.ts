import { describe, it, expect, vi, beforeEach } from "vitest";
import { GET } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { successEnvelope, errorEnvelope } from "@/src/lib/api-envelope";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("GET /api/outreach", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path and adapts a successful response", async () => {
    const raw = {
      messages: [
        {
          message_id: "msg-1",
          company_name: "Acme",
          recipient_role_title: "Hiring Manager",
          subject: "Hello",
          body: "Body text",
          status: "draft",
          sent_at: null,
          created_at: "2024-01-01",
        },
      ],
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const response = await GET();

    expect(backendFetch).toHaveBeenCalledWith("/api/outreach");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      messages: [
        {
          messageId: "msg-1",
          companyName: "Acme",
          recipientRoleTitle: "Hiring Manager",
          subject: "Hello",
          body: "Body text",
          status: "draft",
          createdAt: "2024-01-01",
          sentAt: null,
        },
      ],
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("UNAUTHORIZED", "Not logged in", 401), 401),
    );

    const response = await GET();

    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET();

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
