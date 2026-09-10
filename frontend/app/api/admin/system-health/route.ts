import { mapBackendSystemHealth } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, bffSuccess, handleBackendJson } from "@/src/lib/bff-response";
import { isMockMode } from "@/src/lib/mocks/enabled";

const MOCK_SYSTEM_HEALTH = {
  databaseOk: true,
  databaseLatencyMs: 5,
  redisOk: true,
  redisLatencyMs: 2,
  prometheusConfigured: false,
  signals: {},
};

export async function GET() {
  if (isMockMode()) {
    return bffSuccess(MOCK_SYSTEM_HEALTH);
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/system-health");
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendSystemHealth);
}
