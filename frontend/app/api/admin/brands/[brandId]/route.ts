import { NextRequest } from "next/server";
import { mapBackendAdminBrand, toBackendBrandUpdate } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import type { AdminBrandUpdate } from "@/src/lib/types";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ brandId: string }> },
) {
  const { brandId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/brands/${brandId}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminBrand);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ brandId: string }> },
) {
  const { brandId } = await params;
  const body = (await request.json()) as AdminBrandUpdate;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/brands/${brandId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toBackendBrandUpdate(body)),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminBrand);
}
