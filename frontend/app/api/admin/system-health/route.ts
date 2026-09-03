import { mapBackendSystemHealth } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, bffSuccess, handleBackendJson } from "@/src/lib/bff-response";
import { isMockMode } from "@/src/lib/mocks/enabled";

export async function GET() {
  if (isMockMode()) {
    return bffSuccess({
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
    });
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/system-health");
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendSystemHealth);
}
