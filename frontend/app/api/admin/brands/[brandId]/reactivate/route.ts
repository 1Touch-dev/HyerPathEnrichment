import { NextRequest } from "next/server";
import { mapBackendAdminBrand } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ brandId: string }> },
) {
  const { brandId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/brands/${brandId}/reactivate`, {
      method: "POST",
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminBrand);
}
