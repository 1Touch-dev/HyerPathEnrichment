import { NextRequest } from "next/server";
import { mapBackendAdminBrand, toBackendBrandCreate } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { forwardIdempotencyHeader } from "@/src/lib/idempotency";
import type { AdminBrandCreate } from "@/src/lib/types";

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/brands");
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(
    backendResponse,
    (payload: Parameters<typeof mapBackendAdminBrand>[0][]) => payload.map(mapBackendAdminBrand),
  );
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as AdminBrandCreate;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/brands", {
      method: "POST",
      headers: forwardIdempotencyHeader(request, { "Content-Type": "application/json" }),
      body: JSON.stringify(toBackendBrandCreate(body)),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminBrand);
}
