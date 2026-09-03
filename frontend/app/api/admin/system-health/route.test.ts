import { beforeEach, describe, expect, it, vi } from "vitest";
import { successEnvelope } from "@/src/lib/api-envelope";
import { backendFetch } from "@/src/lib/backend-client";
import { isMockMode } from "@/src/lib/mocks/enabled";
import { GET } from "./route";

vi.mock("@/src/lib/backend-client", () => ({
  backendFetch: vi.fn(),
}));

vi.mock("@/src/lib/mocks/enabled", () => ({
  isMockMode: vi.fn(),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("GET /api/admin/system-health", () => {
  beforeEach(() => {
    vi.mocked(backendFetch).mockReset();
    vi.mocked(isMockMode).mockReturnValue(false);
  });

  it("returns deterministic realistic self-checks and golden signals in mock mode", async () => {
    vi.mocked(isMockMode).mockReturnValue(true);

    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual(
      successEnvelope({
        service: "hyrepath-enrichment-mock",
        databaseOk: true,
        databaseLatencyMs: 4.2,
        redisOk: true,
        redisLatencyMs: 1.8,
        prometheusConfigured: true,
        signals: {
          latency: 42,
          traffic: 128,
          errors: 0,
          saturation: 12,
        },
      }),
    );
    expect(backendFetch).not.toHaveBeenCalled();
  });

  it("preserves live proxy mapping when mock mode is disabled", async () => {
    vi.mocked(backendFetch).mockResolvedValue(
      jsonResponse(
        successEnvelope({
          database_ok: true,
          database_latency_ms: 7.5,
          redis_ok: false,
          redis_latency_ms: 9.25,
          prometheus_configured: false,
          signals: {},
        }),
      ),
    );

    const response = await GET();

    expect(backendFetch).toHaveBeenCalledWith("/api/admin/system-health");
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual(
      successEnvelope({
        databaseOk: true,
        databaseLatencyMs: 7.5,
        redisOk: false,
        redisLatencyMs: 9.25,
        prometheusConfigured: false,
        signals: {},
      }),
    );
  });

  it("keeps the service-unavailable response when the live backend cannot be reached", async () => {
    vi.mocked(backendFetch).mockRejectedValue(new Error("network unavailable"));

    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(502);
    expect(body).toMatchObject({
      success: false,
      error: {
        code: "SERVICE_UNAVAILABLE",
        status_code: 502,
      },
    });
  });
});
