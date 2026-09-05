import { NextRequest } from "next/server";
import { BackendUpdateUserStatusRequest, mapBackendAdminUser } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { forwardIdempotencyHeader } from "@/src/lib/idempotency";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ userId: string }> },
) {
  const { userId } = await params;
  const body = (await request.json()) as BackendUpdateUserStatusRequest;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/users/${userId}/status`, {
      method: "PATCH",
      headers: forwardIdempotencyHeader(request, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminUser);
}
