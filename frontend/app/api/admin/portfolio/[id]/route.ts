import { mapBackendAdminPortfolioProfileDetail } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/portfolio/${id}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminPortfolioProfileDetail);
}
