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

describe("POST /api/outreach/drafts", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method/body and adapts a successful response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(successEnvelope({ rq_job_id: "rq-1", message: "queued" }), 202),
    );

    const response = await POST(
      postRequest({
        companyName: "Acme",
        documentId: "doc-1",
        recipientRoleTitle: "Hiring Manager",
        jobMatchId: "m1",
      }),
    );

    expect(backendFetch).toHaveBeenCalledWith("/api/outreach/drafts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_name: "Acme",
        document_id: "doc-1",
        recipient_role_title: "Hiring Manager",
        job_match_id: "m1",
        job_description: null,
        message_type: "email",
        custom_instruction: null,
        strategy: "direct_pitch",
        referral_context: null,
        role_type: null,
        seniority: null,
      }),
    });
    expect(response.status).toBe(202);
    const body = await response.json();
    expect(body.data).toEqual({ rqJobId: "rq-1", message: "queued" });
  });

  it("forwards strategy/referralContext/roleType/seniority to the backend request body", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(successEnvelope({ rq_job_id: "rq-2", message: "queued" }), 202),
    );

    await POST(
      postRequest({
        companyName: "Acme",
        documentId: "doc-1",
        strategy: "warm_referral",
        referralContext: "Met at a conference",
        roleType: "technical",
        seniority: "senior",
      }),
    );

    const forwardedBody = JSON.parse(vi.mocked(backendFetch).mock.calls[0][1]?.body as string);
    expect(forwardedBody.strategy).toBe("warm_referral");
    expect(forwardedBody.referral_context).toBe("Met at a conference");
    expect(forwardedBody.role_type).toBe("technical");
    expect(forwardedBody.seniority).toBe("senior");
  });

  it("returns a validation error when companyName is missing", async () => {
    const response = await POST(postRequest({ documentId: "doc-1" }));

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
  });

  it("returns a validation error when documentId is missing", async () => {
    const response = await POST(postRequest({ companyName: "Acme" }));

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("VALIDATION_ERROR", "Bad request", 400), 400),
    );

    const response = await POST(postRequest({ companyName: "Acme", documentId: "doc-1" }));

    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(postRequest({ companyName: "Acme", documentId: "doc-1" }));

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
