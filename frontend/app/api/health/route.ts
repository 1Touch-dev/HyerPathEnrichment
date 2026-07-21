import { BackendHealthResponse, mapBackendHealth } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, bffSuccess, handleBackendJson } from "@/src/lib/bff-response";
import { isMockMode } from "@/src/lib/mocks/enabled";

export async function GET() {
  if (isMockMode()) {
    return bffSuccess({ status: "ok", service: "hyrepath-enrichment-mock" });
  }

  try {
    const backendResponse = await backendFetch("/health");
    if (!backendResponse.ok) {
      return bffServiceUnavailable("Health check failed.", 502);
    }
    return handleBackendJson<BackendHealthResponse, ReturnType<typeof mapBackendHealth>>(
      backendResponse,
      mapBackendHealth,
    );
  } catch {
    return bffServiceUnavailable();
  }
}
