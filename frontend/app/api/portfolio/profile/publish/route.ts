import { adaptPortfolioProfile } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/portfolio/profile/publish", {
      method: "POST",
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptPortfolioProfile);
}
