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

function postRequest(body: unknown) {
  return new NextRequest("http://localhost/api/x", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const params = { params: Promise.resolve({ documentId: "doc-1" }) };

describe("POST /api/documents/[documentId]/feedback", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path/method/body and adapts a successful response", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(successEnvelope({ job_id: "job-1" }), 202),
    );

    const response = await POST(postRequest({ targetRole: "Engineer" }), params);

    expect(backendFetch).toHaveBeenCalledWith("/api/documents/doc-1/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_role: "Engineer" }),
    });
    expect(response.status).toBe(202);
    const body = await response.json();
    expect(body.data).toEqual({ jobId: "job-1" });
  });

  it("defaults target_role to null when omitted", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(successEnvelope({ job_id: "job-1" }), 202),
    );

    await POST(postRequest({}), params);

    expect(backendFetch).toHaveBeenCalledWith("/api/documents/doc-1/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_role: null }),
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("VALIDATION_ERROR", "Bad request", 400), 400),
    );

    const response = await POST(postRequest({ targetRole: "Engineer" }), params);

    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await POST(postRequest({ targetRole: "Engineer" }), params);

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});

describe("GET /api/documents/[documentId]/feedback", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
  });

  it("forwards the correct backend path and adapts a successful response", async () => {
    const raw = {
      report_id: "rep-1",
      document_id: "doc-1",
      target_role: "Engineer",
      ats_score: 90,
      strengths: ["Clear"],
      improvements: ["Add metrics"],
      rewritten_bullets: [{ original: "a", rewritten: "b", rationale: "c" }],
      accepted_bullet_indices: [],
      created_at: "2024-01-01",
    };
    vi.mocked(backendFetch).mockResolvedValue(jsonResponse(successEnvelope(raw)));

    const response = await GET(new NextRequest("http://localhost/api/x"), params);

    expect(backendFetch).toHaveBeenCalledWith("/api/documents/doc-1/feedback");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.data).toEqual({
      reportId: "rep-1",
      documentId: "doc-1",
      targetRole: "Engineer",
      atsScore: 90,
      strengths: ["Clear"],
      improvements: ["Add metrics"],
      rewrittenBullets: [{ original: "a", rewritten: "b", rationale: "c" }],
      acceptedBulletIndices: [],
      createdAt: "2024-01-01",
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("NOT_FOUND", "Report not found", 404), 404),
    );

    const response = await GET(new NextRequest("http://localhost/api/x"), params);

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.success).toBe(false);
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET(new NextRequest("http://localhost/api/x"), params);

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
