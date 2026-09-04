import { NextRequest } from "next/server";
import { mapBackendAdminBrand } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { forwardIdempotencyHeader } from "@/src/lib/idempotency";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ brandId: string }> },
) {
  const { brandId } = await params;

  let parsed: unknown = {};
  try {
    parsed = await request.json();
  } catch {
    parsed = {};
  }

  const reason =
    parsed &&
    typeof parsed === "object" &&
    !Array.isArray(parsed) &&
    "reason" in parsed &&
    typeof (parsed as { reason: unknown }).reason === "string" &&
    (parsed as { reason: string }).reason.trim()
      ? (parsed as { reason: string }).reason.trim()
      : undefined;

  const body = reason ? { reason } : {};

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/brands/${brandId}/deactivate`, {
      method: "POST",
      headers: forwardIdempotencyHeader(request, { "Content-Type": "application/json" }),
      body: JSON.stringify(body ?? {}),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminBrand);
}
