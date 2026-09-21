import { beforeEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";
import { backendFetch } from "@/src/lib/backend-client";
import { errorEnvelope, successEnvelope } from "@/src/lib/api-envelope";
import { isMockMode } from "@/src/lib/mocks/enabled";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
  backendFetchPublic: vi.fn(),
}));

vi.mock("@/src/lib/mocks/enabled", () => ({
  isMockMode: vi.fn(() => false),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("GET /api/admin/system-health", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
    vi.mocked(isMockMode).mockReturnValue(false);
  });

  it("returns a stable mock snapshot when frontend mock mode is enabled", async () => {
    vi.mocked(isMockMode).mockReturnValue(true);

    const response = await GET();

    expect(backendFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      success: true,
      data: {
        databaseOk: true,
        databaseLatencyMs: 5,
        redisOk: true,
        redisLatencyMs: 2,
        prometheusConfigured: false,
        signals: {},
      },
    });
  });

  it("adapts a successful backend response in real mode", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(
        successEnvelope({
          database_ok: true,
          database_latency_ms: 7,
          redis_ok: false,
          redis_latency_ms: 11,
          prometheus_configured: true,
          signals: { latency: 120, errors: 0 },
        }),
      ),
    );

    const response = await GET();

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/system-health");
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      success: true,
      data: {
        databaseOk: true,
        databaseLatencyMs: 7,
        redisOk: false,
        redisLatencyMs: 11,
        prometheusConfigured: true,
        signals: { latency: 120, errors: 0 },
      },
    });
  });

  it("translates a failing backend response through backendFailureResponse", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(errorEnvelope("FORBIDDEN", "Not allowed", 403), 403),
    );

    const response = await GET();

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      error: {
        code: "FORBIDDEN",
      },
    });
  });

  it("returns bffServiceUnavailable (502) when backendFetch throws", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network down"));

    const response = await GET();

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      error: {
        code: "SERVICE_UNAVAILABLE",
      },
    });
  });
});
